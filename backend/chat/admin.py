from django.contrib import admin
from .models import Message, MessageReaction, ConversationState


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "receiver", "timestamp", "is_deleted", "is_edited")
    search_fields = ("sender__username", "receiver__username", "content")
    list_filter = ("is_deleted", "is_edited")


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "user", "emoji", "created_at")
    search_fields = ("user__username", "emoji")


@admin.register(ConversationState)
class ConversationStateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "other_user",
        "last_read_at",
        "is_archived",
        "is_muted",
        "updated_at",
    )
    search_fields = ("user__username", "other_user__username")
    list_filter = ("is_archived", "is_muted")
