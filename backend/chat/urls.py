from django.urls import path
from .views import UsersListView, ConversationView, SendMessageView

urlpatterns = [
    path("users/", UsersListView.as_view(), name="chat-users"),
    path("conversation/<int:user_id>/", ConversationView.as_view(), name="conversation"),
    path("send/", SendMessageView.as_view(), name="send-message"),
]
