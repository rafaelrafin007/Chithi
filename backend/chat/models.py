from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="messages_sent", on_delete=models.CASCADE
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="messages_received", on_delete=models.CASCADE
    )
    content = models.TextField(blank=True)  # allow blank if only attachment
    timestamp = models.DateTimeField(auto_now_add=True)

    # Attachment (optional)
    attachment = models.FileField(upload_to="chat/attachments/", null=True, blank=True)

    # NEW fields for edit/delete support
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        preview = (self.content or "")[:20]
        return f"{self.sender} → {self.receiver}: {preview}"


class MessageReaction(models.Model):
    message = models.ForeignKey(Message, related_name="reactions", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="message_reactions", on_delete=models.CASCADE)
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "user")

    def __str__(self):
        return f"{self.user_id} {self.emoji} {self.message_id}"


class ConversationState(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="conversation_states",
        on_delete=models.CASCADE,
    )
    other_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="conversation_states_as_other",
        on_delete=models.CASCADE,
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    muted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "other_user"], name="unique_conversation_state_per_pair"),
            models.CheckConstraint(check=~models.Q(user=models.F("other_user")), name="prevent_self_conversation_state"),
        ]
        indexes = [
            models.Index(fields=["user", "is_archived", "updated_at"]),
            models.Index(fields=["user", "is_muted"]),
            models.Index(fields=["user", "other_user"]),
        ]

    def clean(self):
        if self.user_id and self.other_user_id and self.user_id == self.other_user_id:
            raise ValidationError({"other_user": "Conversation state cannot point to the same user."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def mark_archived(self, archived):
        archived = bool(archived)
        self.is_archived = archived
        self.archived_at = timezone.now() if archived else None

    def mark_muted(self, muted):
        muted = bool(muted)
        self.is_muted = muted
        self.muted_at = timezone.now() if muted else None

    def __str__(self):
        return f"ConversationState user={self.user_id} other={self.other_user_id}"
