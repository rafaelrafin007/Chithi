# users/serializers.py
from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

from .models import Profile, FriendRequest

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = ("display_name", "about", "phone", "avatar", "avatar_url")

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

    def get_avatar_url(self, obj):
        if obj.avatar:
            try:
                url = obj.avatar.url
            except Exception:
                return None
            return self._build_absolute(url)
        return None


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        # Use create_user to properly hash password
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", "") or "",
            password=validated_data["password"],
        )


class UserProfileSerializer(serializers.ModelSerializer):
    # nested profile: name 'profile' matches related_name on Profile
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "profile")


class UserSimpleSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "display_name", "avatar_url")

    def get_display_name(self, obj):
        profile = getattr(obj, "profile", None)
        if profile:
            return getattr(profile, "display_name", None) or obj.username
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
        request = self.context.get("request")
        if url and request:
            try:
                return request.build_absolute_uri(url)
            except Exception:
                return url
        return url


class FriendRequestSerializer(serializers.ModelSerializer):
    from_user = UserSimpleSerializer(read_only=True)
    to_user = UserSimpleSerializer(read_only=True)

    class Meta:
        model = FriendRequest
        fields = ("id", "from_user", "to_user", "status", "created_at", "updated_at")
