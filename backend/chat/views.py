from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Message
from .serializers import UserLiteSerializer, MessageSerializer

# Imports for broadcasting to channels
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

User = get_user_model()


class UsersListView(generics.ListAPIView):
    """All users except me"""
    serializer_class = UserLiteSerializer

    def get_queryset(self):
        return User.objects.exclude(id=self.request.user.id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class ConversationView(APIView):
    """GET messages with the given user_id"""

    def get(self, request, user_id):
        try:
            other = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        qs = Message.objects.filter(
            Q(sender=request.user, receiver=other)
            | Q(sender=other, receiver=request.user)
        ).order_by("timestamp")
        serialized = MessageSerializer(qs, many=True, context={"request": request}).data
        return Response(serialized)


class SendMessageView(APIView):
    """
    POST { receiver: <id>, content: <text>, attachment: <file?> }

    Accepts multipart/form-data for file uploads.
    """
    parser_classes = (MultiPartParser, FormParser)

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

        # Create message in DB
        if attachment:
            msg = Message.objects.create(
                sender=request.user, receiver=receiver, content=content, attachment=attachment
            )
        else:
            msg = Message.objects.create(sender=request.user, receiver=receiver, content=content)

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
