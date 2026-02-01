from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    MeView,
    EmailOrUsernameTokenObtainPairView,
    UsersDirectoryView,
    FriendRequestsView,
    FriendRequestRespondView,
    FriendRequestCancelView,
    FriendsListView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", EmailOrUsernameTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("users/", UsersDirectoryView.as_view(), name="users-directory"),
    path("friend-requests/", FriendRequestsView.as_view(), name="friend-requests"),
    path("friend-requests/<int:request_id>/respond/", FriendRequestRespondView.as_view(), name="friend-request-respond"),
    path("friend-requests/<int:request_id>/cancel/", FriendRequestCancelView.as_view(), name="friend-request-cancel"),
    path("friends/", FriendsListView.as_view(), name="friends-list"),
]
