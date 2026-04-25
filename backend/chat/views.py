from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.utils import OperationalError, ProgrammingError
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.signing import TimestampSigner

from .models import Message, ConversationState
from .serializers import UserLiteSerializer, MessageSerializer
from users.models import are_friends, Block, is_blocked_between

# Imports for broadcasting to channels
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

User = get_user_model()


def _get_or_create_state(user, other_user):
    try:
        state, _ = ConversationState.objects.get_or_create(
            user=user,
            other_user=other_user,
        )
        return state
    except (OperationalError, ProgrammingError):
        # Backward compatibility for databases where chat state migration has not run yet.
        return None


def _mark_conversation_read(user, other_user):
    latest_incoming = (
        Message.objects.filter(sender=other_user, receiver=user)
        .order_by("-timestamp")
        .values_list("timestamp", flat=True)
        .first()
    )
    state = _get_or_create_state(user, other_user)
    if state is None:
        return None
    if latest_incoming and (not state.last_read_at or latest_incoming > state.last_read_at):
        state.last_read_at = latest_incoming
        state.save(update_fields=["last_read_at", "updated_at"])
    return state


def _touch_state_for_new_message(sender, receiver, message_timestamp):
    sender_state = _get_or_create_state(sender, receiver)
    if sender_state is None:
        return
    changed_sender_fields = []
    if not sender_state.last_read_at or message_timestamp > sender_state.last_read_at:
        sender_state.last_read_at = message_timestamp
        changed_sender_fields.append("last_read_at")
    if sender_state.is_archived:
        sender_state.mark_archived(False)
        changed_sender_fields.extend(["is_archived", "archived_at"])
    if changed_sender_fields:
        sender_state.save(update_fields=changed_sender_fields + ["updated_at"])

    receiver_state = _get_or_create_state(receiver, sender)
    if receiver_state.is_archived:
        receiver_state.mark_archived(False)
        receiver_state.save(update_fields=["is_archived", "archived_at", "updated_at"])


class UsersListView(generics.ListAPIView):
    """All users except me"""
    serializer_class = UserLiteSerializer

    def get_queryset(self):
        # Only friends should appear in chat list
        from users.models import FriendRequest
        friend_ids = set()
        accepted = FriendRequest.objects.filter(
            status=FriendRequest.STATUS_ACCEPTED,
            from_user__in=[self.request.user],
        ) | FriendRequest.objects.filter(
            status=FriendRequest.STATUS_ACCEPTED,
            to_user__in=[self.request.user],
        )
        for fr in accepted:
            if fr.from_user_id == self.request.user.id:
                friend_ids.add(fr.to_user_id)
            else:
                friend_ids.add(fr.from_user_id)
        return User.objects.filter(id__in=list(friend_ids)).select_related("profile")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        me = self.request.user
        users = list(getattr(self, "_cached_queryset", self.get_queryset()))
        friend_ids = [u.id for u in users]

        state_map = {}
        peer_last_read_map = {}
        if friend_ids:
            try:
                state_qs = ConversationState.objects.filter(user=me, other_user_id__in=friend_ids)
                state_map = {state.other_user_id: state for state in state_qs}

                # Track counterpart read timestamps for sender-side read receipts.
                peer_state_qs = ConversationState.objects.filter(user_id__in=friend_ids, other_user=me).values(
                    "user_id", "last_read_at"
                )
                peer_last_read_map = {row["user_id"]: row["last_read_at"] for row in peer_state_qs}
            except (OperationalError, ProgrammingError):
                # Legacy DBs without chat_conversationstate table should still list conversations.
                state_map = {}
                peer_last_read_map = {}

        incoming_rows = Message.objects.filter(receiver=me, sender_id__in=friend_ids).values("sender_id", "timestamp")
        unread_count_map = {uid: 0 for uid in friend_ids}
        for row in incoming_rows:
            sender_id = row["sender_id"]
            ts = row["timestamp"]
            last_read = getattr(state_map.get(sender_id), "last_read_at", None)
            if not last_read or ts > last_read:
                unread_count_map[sender_id] = unread_count_map.get(sender_id, 0) + 1

        # Latest message by conversation partner in one pass.
        message_qs = (
            Message.objects.filter(
                Q(sender=me, receiver_id__in=friend_ids)
                | Q(receiver=me, sender_id__in=friend_ids)
            )
            .select_related("sender", "sender__profile", "receiver", "receiver__profile")
            .order_by("-timestamp")
        )
        last_message_map = {}
        for msg in message_qs:
            other_id = msg.receiver_id if msg.sender_id == me.id else msg.sender_id
            if other_id not in last_message_map:
                last_message_map[other_id] = msg
            if len(last_message_map) == len(friend_ids):
                break

        blocked_by_me_ids = set(
            Block.objects.filter(blocker=me, blocked_id__in=friend_ids).values_list("blocked_id", flat=True)
        )
        blocked_me_ids = set(
            Block.objects.filter(blocked=me, blocker_id__in=friend_ids).values_list("blocker_id", flat=True)
        )

        context["request"] = self.request
        context["conversation_state_map"] = state_map
        context["peer_last_read_map"] = peer_last_read_map
        context["unread_count_map"] = unread_count_map
        context["last_message_map"] = last_message_map
        context["blocked_by_me_ids"] = blocked_by_me_ids
        context["blocked_me_ids"] = blocked_me_ids
        return context

    def list(self, request, *args, **kwargs):
        queryset = list(self.get_queryset())
        self._cached_queryset = queryset
        serializer = self.get_serializer(queryset, many=True)
        payload = serializer.data

        archived_param = str(request.query_params.get("archived", "")).lower()
        archived_requested = archived_param in {"1", "true", "yes"}
        if archived_requested:
            payload = [item for item in payload if item.get("is_archived")]
        else:
            payload = [item for item in payload if not item.get("is_archived")]

        payload.sort(
            key=lambda item: item.get("last_message_at") or "",
            reverse=True,
        )
        return Response(payload)


class ConversationView(APIView):
    """GET messages with the given user_id"""

    def get(self, request, user_id):
        try:
            other = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)
        if not are_friends(request.user, other):
            return Response({"detail": "Not friends"}, status=403)

        if request.query_params.get("mark_read", "1") != "0":
            _mark_conversation_read(request.user, other)

        peer_state = None
        try:
            peer_state = ConversationState.objects.filter(user=other, other_user=request.user).only("last_read_at").first()
        except (OperationalError, ProgrammingError):
            peer_state = None
        qs = Message.objects.filter(
            Q(sender=request.user, receiver=other)
            | Q(sender=other, receiver=request.user)
        ).order_by("timestamp")
        serialized = MessageSerializer(
            qs,
            many=True,
            context={
                "request": request,
                "peer_last_read_at": getattr(peer_state, "last_read_at", None),
            },
        ).data
        return Response(serialized)


class ConversationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        try:
            other = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)
        if not are_friends(request.user, other):
            return Response({"detail": "Not friends"}, status=403)
        state = _mark_conversation_read(request.user, other)
        if state is None:
            return Response(
                {
                    "detail": "Conversation marked as read.",
                    "last_read_at": None,
                },
                status=200,
            )
        return Response(
            {
                "detail": "Conversation marked as read.",
                "last_read_at": state.last_read_at,
            },
            status=200,
        )


class ConversationArchiveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        try:
            other = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)
        if not are_friends(request.user, other):
            return Response({"detail": "Not friends"}, status=403)
        state = _get_or_create_state(request.user, other)
        if state is None:
            return Response({"detail": "Conversation state storage is temporarily unavailable."}, status=503)
        state.mark_archived(True)
        state.save(update_fields=["is_archived", "archived_at", "updated_at"])
        return Response({"detail": "Conversation archived.", "is_archived": True}, status=200)


class ConversationUnarchiveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        try:
            other = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)
        if not are_friends(request.user, other):
            return Response({"detail": "Not friends"}, status=403)
        state = _get_or_create_state(request.user, other)
        if state is None:
            return Response({"detail": "Conversation state storage is temporarily unavailable."}, status=503)
        state.mark_archived(False)
        state.save(update_fields=["is_archived", "archived_at", "updated_at"])
        return Response({"detail": "Conversation restored.", "is_archived": False}, status=200)


class ConversationMuteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        try:
            other = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)
        if not are_friends(request.user, other):
            return Response({"detail": "Not friends"}, status=403)
        state = _get_or_create_state(request.user, other)
        if state is None:
            return Response({"detail": "Conversation state storage is temporarily unavailable."}, status=503)
        state.mark_muted(True)
        state.save(update_fields=["is_muted", "muted_at", "updated_at"])
        return Response({"detail": "Conversation muted.", "is_muted": True}, status=200)


class ConversationUnmuteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        try:
            other = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)
        if not are_friends(request.user, other):
            return Response({"detail": "Not friends"}, status=403)
        state = _get_or_create_state(request.user, other)
        if state is None:
            return Response({"detail": "Conversation state storage is temporarily unavailable."}, status=503)
        state.mark_muted(False)
        state.save(update_fields=["is_muted", "muted_at", "updated_at"])
        return Response({"detail": "Conversation unmuted.", "is_muted": False}, status=200)


class SendMessageView(APIView):
    """
    POST { receiver: <id>, content: <text>, attachment: <file?> }

    Accepts multipart/form-data for file uploads.
    """
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request):
        receiver_id = request.data.get("receiver")
        content = (request.data.get("content") or "").strip()
        attachment = request.FILES.get("attachment")

        if not receiver_id:
            return Response({"detail": "receiver is required"}, status=400)

        # If no content and no attachment -> bad request
        if not content and not attachment:
            return Response({"detail": "content or attachment is required"}, status=400)

        try:
            receiver = User.objects.get(pk=receiver_id)
        except User.DoesNotExist:
            return Response({"detail": "Receiver not found"}, status=404)
        if not are_friends(request.user, receiver):
            return Response({"detail": "Not friends"}, status=403)
        if is_blocked_between(request.user, receiver):
            return Response(
                {"detail": "Messaging is unavailable because one user has blocked the other."},
                status=403,
            )

        # Create message in DB
        if attachment:
            msg = Message.objects.create(
                sender=request.user, receiver=receiver, content=content, attachment=attachment
            )
        else:
            msg = Message.objects.create(sender=request.user, receiver=receiver, content=content)
        _touch_state_for_new_message(request.user, receiver, msg.timestamp)

        # Serialize message to return and to broadcast
        serialized = MessageSerializer(msg, context={"request": request}).data

        # Broadcast to Channels group so WS clients receive this message immediately
        try:
            lo, hi = sorted([request.user.id, receiver.id])
            room_group_name = f"chat_{lo}_{hi}"
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {"type": "chat.message", "data": serialized},
            )
            # Also notify receiver personal group so their sidebar updates
            async_to_sync(channel_layer.group_send)(
                f"user_{receiver.id}",
                {"type": "chat.sidebar", "data": serialized},
            )
        except Exception:
            # Don't fail the HTTP response if broadcasting fails.
            import logging
            logging.exception("Failed to broadcast chat message to channel layer")

        return Response(serialized, status=status.HTTP_201_CREATED)


class WSTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        signer = TimestampSigner(salt="ws-token")
        token = signer.sign(str(request.user.id))
        return Response({"ws_token": token})
