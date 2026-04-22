import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Q

from .models import Comment, Follow, Post, PostLike
from .social_serializers import CommentReadSerializer, PostReadSerializer

logger = logging.getLogger(__name__)

SOCIAL_GLOBAL_GROUP = "social_global"
SOCIAL_USER_GROUP_PREFIX = "social_user_"


def social_user_group(user_id):
    return f"{SOCIAL_USER_GROUP_PREFIX}{user_id}"


def recipient_user_ids_for_post(post):
    if post.visibility == Post.VISIBILITY_PUBLIC:
        return None
    if post.visibility == Post.VISIBILITY_PRIVATE:
        return {post.author_id}
    follower_ids = set(
        Follow.objects.filter(following_id=post.author_id).values_list("follower_id", flat=True)
    )
    follower_ids.add(post.author_id)
    return follower_ids


def like_count_for_post(post_id):
    return PostLike.objects.filter(post_id=post_id).count()


def comment_count_for_post(post_id):
    return Comment.objects.filter(post_id=post_id, is_deleted=False).count()


def serialize_post_for_realtime(post, request=None):
    queryset = (
        Post.objects.filter(pk=post.pk)
        .select_related("author", "author__profile")
        .prefetch_related("media")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", filter=Q(comments__is_deleted=False), distinct=True),
        )
    )
    instance = queryset.first() or post
    data = PostReadSerializer(instance, context={"request": request}).data
    # Realtime events should not leak another user's per-request like state.
    data["is_liked_by_me"] = False
    return data


def serialize_comment_for_realtime(comment, request=None):
    queryset = Comment.objects.filter(pk=comment.pk).select_related("author", "author__profile", "parent_comment")
    instance = queryset.first() or comment
    return CommentReadSerializer(instance, context={"request": request}).data


def post_update_payload(post, request=None):
    data = serialize_post_for_realtime(post, request=request)
    return {
        "id": data.get("id"),
        "content": data.get("content"),
        "visibility": data.get("visibility"),
        "updated_at": data.get("updated_at"),
        "is_edited": data.get("is_edited"),
        "media": data.get("media", []),
    }


def broadcast_event_for_post(post, payload):
    recipient_ids = recipient_user_ids_for_post(post)
    if recipient_ids is None:
        _send_to_group(SOCIAL_GLOBAL_GROUP, payload)
        return
    for user_id in recipient_ids:
        _send_to_group(social_user_group(user_id), payload)


def _send_to_group(group_name, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "social.event",
                "payload": payload,
            },
        )
    except Exception:
        logger.exception("Failed to broadcast social event to group %s", group_name)
