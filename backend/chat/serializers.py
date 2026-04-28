# chat/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Message, MessageReaction
from django.db.models import Q
import os
import mimetypes
from django.utils.dateparse import parse_datetime

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    receiver = serializers.SerializerMethodField()
    # New fields
    attachment_url = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()
    attachment_type = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    read = serializers.SerializerMethodField()
    delivered = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "sender",
            "receiver",
            "content",
            "timestamp",
            "is_edited",
            "edited_at",
            "is_deleted",
            "attachment_url",
            "attachment_name",
            "attachment_type",
            "reactions",
            "read",
            "delivered",
        )

    def _build_absolute(self, url):
        # Build absolute URL using request if present, otherwise using base_url from context.
        if not url:
            return None
        request = self.context.get("request")
        base = self.context.get("base_url")
        try:
            if request:
                return request.build_absolute_uri(url)
            if base:
                # ensure no double slashes
                if url.startswith("/"):
                    return base.rstrip("/") + url
                return base.rstrip("/") + "/" + url
        except Exception:
            pass
        return url

    def get_sender(self, obj):
        # include id, username, display_name, avatar_url
        s = obj.sender
        profile = getattr(s, "profile", None)
        display_name = None
        avatar_url = None
        if profile is not None:
            display_name = getattr(profile, "display_name", None) or None
            avatar_field = getattr(profile, "avatar", None)
            if avatar_field:
                try:
                    avatar_url = avatar_field.url
                except Exception:
                    avatar_url = None
        # fallback to top-level fields
        display_name = display_name or getattr(s, "display_name", None) or s.username
        if not avatar_url:
            # maybe user has avatar_url attribute on model or serializer context provided it
            avatar_url = getattr(s, "avatar_url", None) or None
        avatar_url = self._build_absolute(avatar_url) if avatar_url else None
        return {"id": s.id, "username": s.username, "display_name": display_name, "avatar_url": avatar_url}

    def get_receiver(self, obj):
        r = obj.receiver
        profile = getattr(r, "profile", None)
        display_name = None
        avatar_url = None
        if profile is not None:
            display_name = getattr(profile, "display_name", None) or None
            avatar_field = getattr(profile, "avatar", None)
            if avatar_field:
                try:
                    avatar_url = avatar_field.url
                except Exception:
                    avatar_url = None
        display_name = display_name or getattr(r, "display_name", None) or r.username
        if not avatar_url:
            avatar_url = getattr(r, "avatar_url", None) or None
        avatar_url = self._build_absolute(avatar_url) if avatar_url else None
        return {"id": r.id, "username": r.username, "display_name": display_name, "avatar_url": avatar_url}

    def get_attachment_url(self, obj):
        if not getattr(obj, "attachment", None):
            return None
        try:
            url = obj.attachment.url
        except Exception:
            return None
        return self._build_absolute(url)

    def get_attachment_name(self, obj):
        if not getattr(obj, "attachment", None):
            return None
        return os.path.basename(getattr(obj.attachment, "name", "") or "")

    def get_attachment_type(self, obj):
        if not getattr(obj, "attachment", None):
            return None
        mimetype, _ = mimetypes.guess_type(getattr(obj.attachment, "name", "") or "")
        return mimetype  # e.g. "image/png" or "application/pdf"

    def get_reactions(self, obj):
        qs = MessageReaction.objects.filter(message=obj).values_list("emoji", "user_id")
        by_emoji = {}
        for emoji, user_id in qs:
            entry = by_emoji.setdefault(emoji, {"emoji": emoji, "count": 0, "users": []})
            entry["count"] += 1
            entry["users"].append(user_id)
        return list(by_emoji.values())

    def get_read(self, obj):
        value = getattr(obj, "read", None)
        if value is not None:
            return bool(value)

        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        if not viewer or not viewer.is_authenticated:
            return False

        # Incoming messages are considered read by definition for the current viewer.
        if obj.sender_id != viewer.id:
            return True

        peer_last_read_at = self.context.get("peer_last_read_at")
        if peer_last_read_at is None:
            peer_last_read_map = self.context.get("peer_last_read_map") or {}
            peer_last_read_at = peer_last_read_map.get(obj.receiver_id)
        if isinstance(peer_last_read_at, str):
            peer_last_read_at = parse_datetime(peer_last_read_at)
        if not peer_last_read_at:
            return False
        return obj.timestamp <= peer_last_read_at

    def get_delivered(self, obj):
        value = getattr(obj, "delivered", None)
        if value is not None:
            return bool(value)
        return True


class UserLiteSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()
    is_archived = serializers.SerializerMethodField()
    is_muted = serializers.SerializerMethodField()
    is_deleted = serializers.SerializerMethodField()
    is_blocked_by_me = serializers.SerializerMethodField()
    has_blocked_me = serializers.SerializerMethodField()
    can_message = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "display_name",
            "avatar_url",
            "last_message",
            "last_message_at",
            "unread",
            "is_archived",
            "is_muted",
            "is_deleted",
            "is_blocked_by_me",
            "has_blocked_me",
            "can_message",
        )

    def _build_absolute(self, url):
        if not url:
            return None
        request = self.context.get("request")
        base = self.context.get("base_url")
        try:
            if request:
                return request.build_absolute_uri(url)
            if base:
                if url.startswith("/"):
                    return base.rstrip("/") + url
                return base.rstrip("/") + "/" + url
        except Exception:
            pass
        return url

    def get_display_name(self, obj):
        profile = getattr(obj, "profile", None)
        if profile:
            return getattr(profile, "display_name", None) or obj.username
        # fallback if user object has display_name
        return getattr(obj, "display_name", None) or obj.username

    def get_avatar_url(self, obj):
        profile = getattr(obj, "profile", None)
        url = None
        if profile:
            avatar_field = getattr(profile, "avatar", None)
            if avatar_field:
                try:
                    url = avatar_field.url
                except Exception:
                    url = None
        if not url:
            url = getattr(obj, "avatar_url", None) or None
        return self._build_absolute(url) if url else None

    def get_last_message(self, obj):
        message_map = self.context.get("last_message_map") or {}
        msg = message_map.get(obj.id)
        if msg is None:
            request = self.context.get("request")
            if not request or not request.user.is_authenticated:
                return None
            msg = (
                Message.objects.filter(
                    Q(sender=request.user, receiver=obj)
                    | Q(sender=obj, receiver=request.user)
                )
                .order_by("-timestamp")
                .first()
            )
        if not msg:
            return None
        serializer_context = dict(self.context)
        peer_last_read_map = self.context.get("peer_last_read_map") or {}
        serializer_context["peer_last_read_at"] = peer_last_read_map.get(obj.id)
        return MessageSerializer(msg, context=serializer_context).data

    def get_last_message_at(self, obj):
        message_map = self.context.get("last_message_map") or {}
        msg = message_map.get(obj.id)
        return getattr(msg, "timestamp", None) if msg else None

    def get_unread(self, obj):
        unread_map = self.context.get("unread_count_map") or {}
        return int(unread_map.get(obj.id, 0))

    def _state_for(self, obj):
        state_map = self.context.get("conversation_state_map") or {}
        return state_map.get(obj.id)

    def get_is_archived(self, obj):
        state = self._state_for(obj)
        return bool(getattr(state, "is_archived", False))

    def get_is_muted(self, obj):
        state = self._state_for(obj)
        return bool(getattr(state, "is_muted", False))

    def get_is_deleted(self, obj):
        state = self._state_for(obj)
        return bool(
            state
            and getattr(state, "is_archived", False)
            and getattr(state, "archived_at", None)
            and getattr(state, "muted_at", None)
            and state.archived_at == state.muted_at
            and state.archived_at.year >= 2099
        )

    def get_is_blocked_by_me(self, obj):
        ids = self.context.get("blocked_by_me_ids") or set()
        return obj.id in ids

    def get_has_blocked_me(self, obj):
        ids = self.context.get("blocked_me_ids") or set()
        return obj.id in ids

    def get_can_message(self, obj):
        return not self.get_is_blocked_by_me(obj) and not self.get_has_blocked_me(obj)
