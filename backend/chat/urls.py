from django.urls import path
from .views import (
    UsersListView,
    ConversationView,
    ConversationMarkReadView,
    ConversationArchiveView,
    ConversationUnarchiveView,
    ConversationMuteView,
    ConversationUnmuteView,
    ConversationDeleteView,
    SendMessageView,
    WSTokenView,
)

urlpatterns = [
    path("users/", UsersListView.as_view(), name="chat-users"),
    path("conversation/<int:user_id>/", ConversationView.as_view(), name="conversation"),
    path("conversation/<int:user_id>/read/", ConversationMarkReadView.as_view(), name="conversation-mark-read"),
    path("conversation/<int:user_id>/archive/", ConversationArchiveView.as_view(), name="conversation-archive"),
    path("conversation/<int:user_id>/unarchive/", ConversationUnarchiveView.as_view(), name="conversation-unarchive"),
    path("conversation/<int:user_id>/mute/", ConversationMuteView.as_view(), name="conversation-mute"),
    path("conversation/<int:user_id>/unmute/", ConversationUnmuteView.as_view(), name="conversation-unmute"),
    path("conversation/<int:user_id>/delete/", ConversationDeleteView.as_view(), name="conversation-delete"),
    path("send/", SendMessageView.as_view(), name="send-message"),
    path("ws-token/", WSTokenView.as_view(), name="chat-ws-token"),
]
