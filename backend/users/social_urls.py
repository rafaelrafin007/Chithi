from django.urls import path

from .social_views import (
    PublicProfileView,
    FollowUserView,
    UnfollowUserView,
    FollowersListView,
    FollowingListView,
    FeedView,
    ProfilePostsView,
    PostDetailView,
    LikePostView,
    UnlikePostView,
    CommentListCreateView,
    CommentDetailView,
)

urlpatterns = [
    # Profiles / social graph
    path("profiles/<str:identifier>/", PublicProfileView.as_view(), name="social-profile-detail"),
    path("profiles/<str:identifier>/follow/", FollowUserView.as_view(), name="social-follow-user"),
    path("profiles/<str:identifier>/unfollow/", UnfollowUserView.as_view(), name="social-unfollow-user"),
    path("profiles/<str:identifier>/followers/", FollowersListView.as_view(), name="social-followers-list"),
    path("profiles/<str:identifier>/following/", FollowingListView.as_view(), name="social-following-list"),
    # Posts
    path("feed/", FeedView.as_view(), name="social-feed"),
    path("profiles/<str:identifier>/posts/", ProfilePostsView.as_view(), name="social-profile-posts"),
    path("posts/<int:post_id>/", PostDetailView.as_view(), name="social-post-detail"),
    # Likes
    path("posts/<int:post_id>/like/", LikePostView.as_view(), name="social-post-like"),
    path("posts/<int:post_id>/unlike/", UnlikePostView.as_view(), name="social-post-unlike"),
    # Comments
    path("posts/<int:post_id>/comments/", CommentListCreateView.as_view(), name="social-comment-list-create"),
    path("comments/<int:comment_id>/", CommentDetailView.as_view(), name="social-comment-detail"),
]
