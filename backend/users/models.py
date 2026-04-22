from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from django.db.models.signals import post_save

class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    display_name = models.CharField(max_length=150, blank=True)
    about = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name or self.user.username or str(self.user.id)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile(sender, instance, created, **kwargs):
    # create profile for new users
    if created:
        Profile.objects.create(user=instance)


class FriendRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_DECLINED, "Declined"),
    ]

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="friend_requests_sent",
        on_delete=models.CASCADE,
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="friend_requests_received",
        on_delete=models.CASCADE,
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("from_user", "to_user")

    def __str__(self):
        return f"{self.from_user_id} -> {self.to_user_id} ({self.status})"


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="following_relations",
        on_delete=models.CASCADE,
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="follower_relations",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["follower", "following"], name="unique_follow_relation"),
            models.CheckConstraint(check=~models.Q(follower=models.F("following")), name="prevent_self_follow"),
        ]

    def clean(self):
        if self.follower_id and self.following_id and self.follower_id == self.following_id:
            raise ValidationError({"following": "You cannot follow yourself."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.follower_id} -> {self.following_id}"


class Block(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="blocks_initiated",
        on_delete=models.CASCADE,
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="blocks_received",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block_relation"),
            models.CheckConstraint(check=~models.Q(blocker=models.F("blocked")), name="prevent_self_block"),
        ]
        indexes = [
            models.Index(fields=["blocker", "created_at"]),
            models.Index(fields=["blocked", "created_at"]),
        ]

    def clean(self):
        if self.blocker_id and self.blocked_id and self.blocker_id == self.blocked_id:
            raise ValidationError({"blocked": "You cannot block yourself."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.blocker_id} blocked {self.blocked_id}"


class Post(models.Model):
    VISIBILITY_PUBLIC = "public"
    VISIBILITY_FOLLOWERS_ONLY = "followers_only"
    VISIBILITY_PRIVATE = "private"

    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, "Public"),
        (VISIBILITY_FOLLOWERS_ONLY, "Followers Only"),
        (VISIBILITY_PRIVATE, "Private"),
    ]

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="posts",
        on_delete=models.CASCADE,
    )
    content = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_PUBLIC)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        has_text = bool((self.content or "").strip())
        has_media = bool(self.pk and self.media.exists())
        if not has_text and not has_media:
            raise ValidationError({"content": "Post cannot be empty if no media is attached."})

    def __str__(self):
        return f"Post {self.id} by {self.author_id}"


class PostMedia(models.Model):
    MEDIA_TYPE_IMAGE = "image"

    MEDIA_TYPE_CHOICES = [
        (MEDIA_TYPE_IMAGE, "Image"),
    ]

    post = models.ForeignKey(Post, related_name="media", on_delete=models.CASCADE)
    file = models.FileField(upload_to="social/posts/")
    media_type = models.CharField(max_length=16, choices=MEDIA_TYPE_CHOICES, default=MEDIA_TYPE_IMAGE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"PostMedia {self.id} for post {self.post_id}"


class PostLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="post_likes",
        on_delete=models.CASCADE,
    )
    post = models.ForeignKey(
        Post,
        related_name="likes",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_post_like"),
        ]

    def __str__(self):
        return f"{self.user_id} likes {self.post_id}"


class Comment(models.Model):
    post = models.ForeignKey(Post, related_name="comments", on_delete=models.CASCADE)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="comments",
        on_delete=models.CASCADE,
    )
    content = models.TextField()
    parent_comment = models.ForeignKey(
        "self",
        related_name="replies",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment {self.id} on post {self.post_id}"


class Notification(models.Model):
    TYPE_FOLLOW = "follow"
    TYPE_POST_LIKE = "post_like"
    TYPE_POST_COMMENT = "post_comment"

    TYPE_CHOICES = [
        (TYPE_FOLLOW, "Follow"),
        (TYPE_POST_LIKE, "Post Like"),
        (TYPE_POST_COMMENT, "Post Comment"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="notifications_received",
        on_delete=models.CASCADE,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="notifications_sent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    target_post = models.ForeignKey(
        Post,
        related_name="notifications",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    target_comment = models.ForeignKey(
        Comment,
        related_name="notifications",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
            models.Index(fields=["type", "created_at"]),
        ]

    def __str__(self):
        return f"Notification {self.id} -> user {self.recipient_id}"


class Report(models.Model):
    STATUS_OPEN = "open"
    STATUS_REVIEWED = "reviewed"
    STATUS_DISMISSED = "dismissed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_REVIEWED, "Reviewed"),
        (STATUS_DISMISSED, "Dismissed"),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="reports_created",
        on_delete=models.CASCADE,
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="reports_received",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    target_post = models.ForeignKey(
        Post,
        related_name="reports",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    reason = models.CharField(max_length=64)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["reporter", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def clean(self):
        has_user = bool(self.target_user_id)
        has_post = bool(self.target_post_id)
        if has_user == has_post:
            raise ValidationError("Report must target exactly one of user or post.")
        if not (self.reason or "").strip():
            raise ValidationError({"reason": "Reason is required."})
        if self.target_user_id and self.reporter_id and self.target_user_id == self.reporter_id:
            raise ValidationError({"target_user": "You cannot report yourself."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Report {self.id} by {self.reporter_id}"


def are_friends(user_a, user_b):
    if not user_a or not user_b:
        return False
    return FriendRequest.objects.filter(
        status=FriendRequest.STATUS_ACCEPTED,
        from_user__in=[user_a, user_b],
        to_user__in=[user_a, user_b],
    ).exists()


def is_blocked_between(user_a, user_b):
    if not user_a or not user_b:
        return False
    if getattr(user_a, "id", None) == getattr(user_b, "id", None):
        return False
    return Block.objects.filter(
        models.Q(blocker=user_a, blocked=user_b) | models.Q(blocker=user_b, blocked=user_a)
    ).exists()
