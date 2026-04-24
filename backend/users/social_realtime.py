import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count, Q
from django.contrib.auth import get_user_model

from .models import Block, Comment, Follow, Post, PostLike
from .social_serializers import CommentReadSerializer, PostReadSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

SOCIAL_GLOBAL_GROUP = "social_global"
SOCIAL_USER_GROUP_PREFIX = "social_user_"


def social_user_group(user_id):
    return f"{SOCIAL_USER_GROUP_PREFIX}{user_id}"


def recipient_user_ids_for_post(post):
    blocked_ids = set(
        Block.objects.filter(
            Q(blocker_id=post.author_id) | Q(blocked_id=post.author_id)
        ).values_list("blocker_id", "blocked_id")
    )
    blocked_user_ids = set()
    for blocker_id, blocked_id in blocked_ids:
        if blocker_id == post.author_id:
            blocked_user_ids.add(blocked_id)
        if blocked_id == post.author_id:
            blocked_user_ids.add(blocker_id)

    if post.visibility == Post.VISIBILITY_PUBLIC:
        recipients = set(User.objects.values_list("id", flat=True))
        recipients.discard(None)
        recipients -= blocked_user_ids
        recipients.add(post.author_id)
        return recipients
    if post.visibility == Post.VISIBILITY_PRIVATE:
        return {post.author_id}
    follower_ids = set(
        Follow.objects.filter(following_id=post.author_id).values_list("follower_id", flat=True)
    )
    follower_ids -= blocked_user_ids
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
    for user_id in recipient_ids:
        _send_to_group(social_user_group(user_id), payload)


def broadcast_notification_event(recipient_id, payload):
    if not recipient_id:
        return
    _send_to_group(social_user_group(recipient_id), payload)


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
