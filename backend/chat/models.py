from django.db import models
from django.conf import settings
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
        unique_together = ("message", "user", "emoji")

    def __str__(self):
        return f"{self.user_id} {self.emoji} {self.message_id}"
