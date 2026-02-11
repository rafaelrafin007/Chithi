# chat/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Message, MessageReaction
from django.db.models import Q
import os
import mimetypes

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    receiver = serializers.SerializerMethodField()
    # New fields
    attachment_url = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()
    attachment_type = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()

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


class UserLiteSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "display_name", "avatar_url", "last_message")

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
        # context may include 'request' and/or 'base_url'
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            # still attempt to fetch last message, but if no authenticated request available,
            # skip to be safe
            # However previous behavior returned None if no request authenticated; keep that.
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
        # include same context so attachment/avatar urls are absolute when possible
        return MessageSerializer(msg, context=self.context).data if msg else None
