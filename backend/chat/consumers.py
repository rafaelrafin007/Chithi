# chat/consumers.py
import json
import logging
import asyncio
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

ONLINE_USERS = set()
ONLINE_LOCK = asyncio.Lock()


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for chat.

    Extended with support for:
      - editing messages (type: "edit", payload: {"message_id": <id>, "content": "<text>"} )
      - deleting messages (type: "delete", payload: {"message_id": <id>})
      - typing/delivered/read etc.

    When a message is soft-deleted we now attempt to clear/delete any attachment
    fields and broadcast the full updated serialized message (chat.message_updated).
    """

    async def connect(self):
        self.user = await self._authenticate_from_querystring()
        if not self.user or not self.user.is_authenticated:
            logger.warning("WebSocket auth failed during connect")
            await self.close(code=4401)
            return

        # other_user_id is the "target" user from the URL (conversation partner)
        self.other_user_id = int(self.scope["url_route"]["kwargs"]["user_id"])
        if not await self._are_friends(self.user.id, self.other_user_id):
            await self.close(code=4403)
            return
        self.room_group_name = await self._room_for_users(self.user.id, self.other_user_id)
        self.user_group_name = f"user_{self.user.id}"

        # join conversation room and personal group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.channel_layer.group_add("presence", self.channel_name)

        await self.accept()

        # mark online and broadcast presence
        async with ONLINE_LOCK:
            ONLINE_USERS.add(self.user.id)
            online_list = list(ONLINE_USERS)
        await self.channel_layer.group_send(
            "presence",
            {"type": "presence.update", "user": self.user.id, "online": True},
        )
        await self.send_json({"type": "presence_sync", "users": online_list})

    async def disconnect(self, code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
        await self.channel_layer.group_discard("presence", self.channel_name)

        if self.user and self.user.is_authenticated:
            async with ONLINE_LOCK:
                ONLINE_USERS.discard(self.user.id)
            await self.channel_layer.group_send(
                "presence",
                {"type": "presence.update", "user": self.user.id, "online": False},
            )
            await self._update_last_seen(self.user)

    async def receive_json(self, content, **kwargs):
        if not self.user or not self.user.is_authenticated:
            return

        event_type = content.get("type")

        # Typing indicator -> broadcast to room
        if event_type == "typing":
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat.typing", "user": self.user.id},
            )
            return

        # Delivered ack -> look up message participants and broadcast ack
        if event_type == "delivered":
            message_id = content.get("message_id")
            if message_id:
                # broadcast to conversation room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "chat.delivered", "user": self.user.id, "message_id": message_id},
                )
                # also find the message to notify its sender/recipient via their personal groups
                sender_id, receiver_id = await self._get_message_participants(message_id)
                if sender_id:
                    await self.channel_layer.group_send(
                        f"user_{sender_id}",
                        {"type": "chat.delivered", "user": self.user.id, "message_id": message_id},
                    )
                if receiver_id:
                    await self.channel_layer.group_send(
                        f"user_{receiver_id}",
                        {"type": "chat.delivered", "user": self.user.id, "message_id": message_id},
                    )
            return

        # Read receipts -> broadcast to room + both users' personal groups
        if event_type == "read":
            last_read = content.get("last_read")
            if last_read:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "chat.read", "user": self.user.id, "last_read": last_read},
                )
                # notify both participants by personal group so sender sees read even if not in the room
                await self.channel_layer.group_send(
                    f"user_{self.user.id}",
                    {"type": "chat.read", "user": self.user.id, "last_read": last_read},
                )
                await self.channel_layer.group_send(
                    f"user_{self.other_user_id}",
                    {"type": "chat.read", "user": self.user.id, "last_read": last_read},
                )
            return

        # EDIT message
        if event_type == "edit":
            message_id = content.get("message_id")
            new_content = (content.get("content") or "").strip()
            if not message_id or new_content is None:
                return

            # Ensure message exists and that current user is the sender
            msg = await self._get_message(message_id)
            if not msg:
                return
            if msg.sender_id != self.user.id:
                # not allowed
                return

            # update message
            updated = await self._edit_message(message_id, new_content)
            if updated:
                payload = await self._serialize_message(updated)
                # broadcast updated message to conversation room
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "chat.message_updated", "data": payload},
                )
            return

        # DELETE message (soft-delete)
        if event_type == "delete":
            message_id = content.get("message_id")
            if not message_id:
                return

            msg = await self._get_message(message_id)
            if not msg:
                return
            if msg.sender_id != self.user.id:
                return

            # perform soft delete and attempt to remove/clear attachments
            updated_msg = await self._soft_delete_message(message_id)
            if updated_msg:
                # Broadcast the full updated serialized message so clients update consistently
                payload = await self._serialize_message(updated_msg)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "chat.message_updated", "data": payload},
                )
            return

        # React to a message
        if event_type == "react":
            message_id = content.get("message_id")
            emoji = (content.get("emoji") or "").strip()
            if not message_id or not emoji:
                return
            updated = await self._toggle_reaction(message_id, self.user.id, emoji)
            if updated is None:
                return
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat.reaction",
                    "message_id": message_id,
                    "emoji": emoji,
                    "user": self.user.id,
                    "action": "added" if updated else "removed",
                },
            )
            return

        # Regular message -> create DB object and broadcast to:
        #  - conversation room (chat.message)
        #  - recipient personal group (chat.sidebar) so they get sidebar update even if not in the room
        text = (content or {}).get("content", "")
        if text is None:
            text = ""
        text = text.strip()
        if not text:
            return

        other = await self._get_user(self.other_user_id)
        if not other:
            return

        # create message in DB (note: your Message model uses `timestamp` auto_now_add)
        msg = await self._create_message(self.user, other, text)
        payload = await self._serialize_message(msg)

        # Broadcast canonical message to conversation room
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat.message", "data": payload},
        )

        # ALSO send a sidebar notification to the receiver's personal group so their sidebar updates
        await self.channel_layer.group_send(
            f"user_{other.id}",
            {"type": "chat.sidebar", "data": payload},
        )

    # ----------------- Event handlers sent to clients -----------------
    async def chat_message(self, event):
        await self.send_json({"type": "message", "data": event["data"]})

    async def chat_sidebar(self, event):
        # Sidebar-only notification: client should update the users list/unread count
        await self.send_json({"type": "sidebar", "data": event["data"]})

    async def chat_typing(self, event):
        await self.send_json({"type": "typing", "user": event.get("user")})

    async def chat_delivered(self, event):
        await self.send_json({
            "type": "delivered",
            "user": event.get("user"),
            "message_id": event.get("message_id"),
        })

    async def chat_read(self, event):
        await self.send_json({
            "type": "read",
            "user": event.get("user"),
            "last_read": event.get("last_read"),
        })

    async def chat_message_updated(self, event):
        # updated message broadcast
        await self.send_json({"type": "message_updated", "data": event["data"]})

    async def chat_message_deleted(self, event):
        # kept for backwards-compatibility (if any code expects message_deleted)
        await self.send_json({"type": "message_deleted", "data": event["data"]})

    async def chat_reaction(self, event):
        await self.send_json({
            "type": "reaction",
            "message_id": event.get("message_id"),
            "emoji": event.get("emoji"),
            "user": event.get("user"),
            "action": event.get("action"),
        })

    async def presence_update(self, event):
        await self.send_json({
            "type": "presence",
            "user": event.get("user"),
            "online": event.get("online"),
        })

    async def friend_request(self, event):
        await self.send_json({
            "type": "friend_request",
            "from_user": event.get("from_user"),
        })

    # ----------------- helpers (lazy imports) -----------------
    async def _authenticate_from_querystring(self):
        try:
            # Prefer short-lived WS token over JWT in querystring.
            from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
            signer = TimestampSigner(salt="ws-token")

            from rest_framework_simplejwt.backends import TokenBackend
            from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
            from django.conf import settings

            query = parse_qs(self.scope.get("query_string", b"").decode())
            ws_token = (query.get("ws_token") or [None])[0]
            if ws_token:
                try:
                    user_id = signer.unsign(ws_token, max_age=60)
                    return await self._get_user(user_id)
                except (BadSignature, SignatureExpired):
                    return None

            token = (query.get("token") or [None])[0]
            if not token:
                return None

            backend = TokenBackend(algorithm="HS256", signing_key=settings.SECRET_KEY)
            data = backend.decode(token, verify=True)
            user_id = data.get("user_id")
            if not user_id:
                return None
            return await self._get_user(user_id)
        except (TokenError, InvalidToken) as e:
            logger.warning(f"JWT auth failed: {e}")
            return None
        except Exception as e:
            logger.exception("Unexpected auth error")
            return None

    @database_sync_to_async
    def _get_user(self, user_id: int):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def _are_friends(self, user_a_id: int, user_b_id: int):
        from users.models import FriendRequest
        return FriendRequest.objects.filter(
            status=FriendRequest.STATUS_ACCEPTED,
            from_user__id__in=[user_a_id, user_b_id],
            to_user__id__in=[user_a_id, user_b_id],
        ).exists()

    @database_sync_to_async
    def _create_message(self, sender, receiver, content: str):
        from .models import Message
        # NOTE: Message has field 'timestamp' auto_now_add; do not pass created_at
        return Message.objects.create(sender=sender, receiver=receiver, content=content)

    @database_sync_to_async
    def _serialize_message(self, message):
        """
        Serialize a Message instance into the same JSON that the REST API
        returns. We pass a `base_url` into serializer context so that
        attachment/avatar urls are absolute and fetchable by the React client.
        """
        from .serializers import MessageSerializer

        # Build base_url from ASGI scope (host header + scheme)
        try:
            # scheme might be 'ws' or 'wss' in scope; map to http(s)
            scope_scheme = (self.scope.get("scheme") or "").lower()
            http_scheme = "https" if scope_scheme in ("wss", "https") else "http"
            # extract host header
            headers = dict((h[0].decode().lower(), h[1].decode()) for h in (self.scope.get("headers") or []))
            host = headers.get("host") or "127.0.0.1:8000"
            base_url = f"{http_scheme}://{host}"
        except Exception:
            base_url = "http://127.0.0.1:8000"

        # Use MessageSerializer with base_url in context (no `request` available here)
        return MessageSerializer(message, context={"base_url": base_url}).data

    @database_sync_to_async
    def _room_for_users(self, a: int, b: int):
        lo, hi = sorted([a, b])
        return f"chat_{lo}_{hi}"

    @database_sync_to_async
    def _update_last_seen(self, user):
        from django.utils import timezone
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

    @database_sync_to_async
    def _get_message_participants(self, message_id: int):
        """
        Return (sender_id, receiver_id) for a message id or (None, None) if not found.
        Used to target personal groups for a delivered ack.
        """
        from .models import Message
        try:
            m = Message.objects.only("sender_id", "receiver_id").get(pk=message_id)
            return (m.sender_id, m.receiver_id)
        except Message.DoesNotExist:
            return (None, None)

    @database_sync_to_async
    def _get_message(self, message_id: int):
        from .models import Message
        try:
            return Message.objects.get(pk=message_id)
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def _toggle_reaction(self, message_id: int, user_id: int, emoji: str):
        from .models import MessageReaction, Message
        try:
            msg = Message.objects.only("id", "sender_id", "receiver_id").get(pk=message_id)
        except Message.DoesNotExist:
            return None
        # ensure user is a participant
        if user_id not in (msg.sender_id, msg.receiver_id):
            return None
        existing = MessageReaction.objects.filter(message_id=message_id, user_id=user_id, emoji=emoji).first()
        if existing:
            existing.delete()
            return False
        MessageReaction.objects.create(message_id=message_id, user_id=user_id, emoji=emoji)
        return True

    @database_sync_to_async
    def _edit_message(self, message_id: int, new_content: str):
        from .models import Message
        from django.utils import timezone
        try:
            m = Message.objects.get(pk=message_id)
            m.content = new_content
            m.is_edited = True
            m.edited_at = timezone.now()
            m.save(update_fields=["content", "is_edited", "edited_at"])
            return m
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def _soft_delete_message(self, message_id: int):
        """
        Soft-delete the message, attempt to clear/remove any attachment fields if present,
        and return the updated model instance (so we can serialize and broadcast it).
        """
        from .models import Message
        from django.utils import timezone
        try:
            m = Message.objects.get(pk=message_id)
            m.content = "This message was deleted"
            m.is_deleted = True
            m.edited_at = timezone.now()

            # If your Message model has attachment fields, try to delete the files and null them.
            # We check attributes dynamically so this code remains safe if fields don't exist.
            changed_fields = ["content", "is_deleted", "edited_at"]

            # Common field names: 'attachment', 'attachment_thumb', 'file'
            # Remove/delete them if present
            if hasattr(m, "attachment"):
                try:
                    if m.attachment:
                        m.attachment.delete(save=False)
                except Exception:
                    logger.exception("Failed to delete message.attachment file")
                m.attachment = None
                changed_fields.append("attachment")

            if hasattr(m, "attachment_thumb"):
                try:
                    if m.attachment_thumb:
                        m.attachment_thumb.delete(save=False)
                except Exception:
                    logger.exception("Failed to delete message.attachment_thumb file")
                m.attachment_thumb = None
                changed_fields.append("attachment_thumb")

            if hasattr(m, "file"):
                try:
                    if m.file:
                        m.file.delete(save=False)
                except Exception:
                    logger.exception("Failed to delete message.file file")
                m.file = None
                changed_fields.append("file")

            m.save(update_fields=changed_fields)
            return m
        except Message.DoesNotExist:
            return None
