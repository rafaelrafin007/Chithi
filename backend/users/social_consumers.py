import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)
SOCIAL_GLOBAL_GROUP = "social_global"
SOCIAL_USER_GROUP_PREFIX = "social_user_"


def social_user_group(user_id):
    return f"{SOCIAL_USER_GROUP_PREFIX}{user_id}"


class SocialConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = await self._authenticate_from_querystring()
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.user_group_name = social_user_group(self.user.id)

        await self.channel_layer.group_add(SOCIAL_GLOBAL_GROUP, self.channel_name)
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
        await self.channel_layer.group_discard(SOCIAL_GLOBAL_GROUP, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Keep consumer one-way for now; realtime sync is server -> client.
        return

    async def social_event(self, event):
        payload = event.get("payload") or {}
        await self.send_json({"type": "social_event", **payload})

    @database_sync_to_async
    def _get_user(self, user_id):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    async def _authenticate_from_querystring(self):
        try:
            from django.conf import settings
            from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
            from rest_framework_simplejwt.backends import TokenBackend
            from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

            signer = TimestampSigner(salt="ws-token")
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
        except (TokenError, InvalidToken):
            return None
        except Exception:
            logger.exception("Unexpected social websocket auth error")
            return None
