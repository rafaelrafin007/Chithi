from django.urls import path
from .views import UsersListView, ConversationView, SendMessageView, WSTokenView

urlpatterns = [
    path("users/", UsersListView.as_view(), name="chat-users"),
    path("conversation/<int:user_id>/", ConversationView.as_view(), name="conversation"),
    path("send/", SendMessageView.as_view(), name="send-message"),
    path("ws-token/", WSTokenView.as_view(), name="chat-ws-token"),
]
