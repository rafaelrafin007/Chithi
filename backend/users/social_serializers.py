from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Block, Post, PostMedia, Comment, Notification, Report
from .serializers import UserSimpleSerializer

User = get_user_model()


class PublicProfileSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    about = serializers.SerializerMethodField()
    followers_count = serializers.IntegerField(read_only=True)
    following_count = serializers.IntegerField(read_only=True)
    posts_count = serializers.IntegerField(read_only=True)
    is_following = serializers.BooleanField(read_only=True)
    is_blocked_by_me = serializers.BooleanField(read_only=True)
    has_blocked_me = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "display_name",
            "avatar_url",
            "about",
            "followers_count",
            "following_count",
            "posts_count",
            "is_following",
            "is_blocked_by_me",
            "has_blocked_me",
        )

    def _build_absolute(self, url):
        if not url:
            return None
        request = self.context.get("request")
        if request:
            try:
                return request.build_absolute_uri(url)
            except Exception:
                return url
        return url

    def get_display_name(self, obj):
        profile = getattr(obj, "profile", None)
        if profile:
            return profile.display_name or obj.username
        return obj.username

    def get_avatar_url(self, obj):
        profile = getattr(obj, "profile", None)
        if not profile or not getattr(profile, "avatar", None):
            return None
        try:
            return self._build_absolute(profile.avatar.url)
        except Exception:
            return None

    def get_about(self, obj):
        profile = getattr(obj, "profile", None)
        return getattr(profile, "about", "") if profile else ""


class PostMediaSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = PostMedia
        fields = ("id", "file_url", "media_type", "created_at")

    def get_file_url(self, obj):
        request = self.context.get("request")
        try:
            url = obj.file.url
        except Exception:
            return None
        if request:
            try:
                return request.build_absolute_uri(url)
            except Exception:
                return url
        return url


class PostWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ("content", "visibility")

    def validate_content(self, value):
        return (value or "").strip()

    def validate_visibility(self, value):
        valid = {v for v, _ in Post.VISIBILITY_CHOICES}
        if value not in valid:
            raise serializers.ValidationError("Invalid visibility.")
        return value

    def validate(self, attrs):
        content = attrs.get("content")
        if content is None and self.instance is not None:
            content = self.instance.content
        content = (content or "").strip()

        uploaded_files = self.context.get("uploaded_files", [])
        has_media = bool(uploaded_files)
        if self.instance is not None:
            has_media = has_media or self.instance.media.exists()

        if not content and not has_media:
            raise serializers.ValidationError("Post cannot be empty if no media is attached.")
        return attrs


class PostReadSerializer(serializers.ModelSerializer):
    author = UserSimpleSerializer(read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    like_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    is_liked_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "content",
            "visibility",
            "created_at",
            "updated_at",
            "is_edited",
            "media",
            "like_count",
            "comment_count",
            "is_liked_by_me",
        )

    def get_like_count(self, obj):
        value = getattr(obj, "like_count", None)
        if value is None:
            return obj.likes.count()
        return value

    def get_comment_count(self, obj):
        value = getattr(obj, "comment_count", None)
        if value is None:
            return obj.comments.filter(is_deleted=False).count()
        return value

    def get_is_liked_by_me(self, obj):
        value = getattr(obj, "is_liked_by_me", None)
        if value is not None:
            return bool(value)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return obj.likes.filter(user=user).exists()


class CommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ("content", "parent_comment")

    def validate_content(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Comment content is required.")
        return value

    def validate_parent_comment(self, value):
        if not value:
            return value
        post = self.context.get("post")
        if post and value.post_id != post.id:
            raise serializers.ValidationError("Reply must belong to the same post.")
        return value


class CommentReadSerializer(serializers.ModelSerializer):
    author = UserSimpleSerializer(read_only=True)
    parent_comment = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "post",
            "author",
            "content",
            "parent_comment",
            "created_at",
            "updated_at",
            "is_deleted",
        )


class NotificationReadSerializer(serializers.ModelSerializer):
    actor = UserSimpleSerializer(read_only=True)
    target_post_id = serializers.IntegerField(source="target_post.id", read_only=True)
    target_comment_id = serializers.IntegerField(source="target_comment.id", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "type",
            "is_read",
            "created_at",
            "actor",
            "target_post_id",
            "target_comment_id",
        )


class ReportWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ("reason", "details")

    def validate_reason(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Reason is required.")
        return value


class BlockReadSerializer(serializers.ModelSerializer):
    blocked_user = UserSimpleSerializer(source="blocked", read_only=True)

    class Meta:
        model = Block
        fields = ("id", "blocked_user", "created_at")
