from django.db.models import Q

from .models import Block, FriendRequest, Follow, Notification, Post
from .social_realtime import broadcast_notification_event
from .social_serializers import NotificationReadSerializer


def create_notification_if_applicable(
    recipient,
    actor,
    notification_type,
    target_post=None,
    target_comment=None,
    dedupe=False,
):
    if not recipient or not actor:
        return None
    if recipient.id == actor.id:
        return None

    lookup = {
        "recipient": recipient,
        "actor": actor,
        "type": notification_type,
        "target_post": target_post,
        "target_comment": target_comment,
    }
    if dedupe:
        notification, created = Notification.objects.get_or_create(defaults={"is_read": False}, **lookup)
        if not created and notification.is_read:
            notification.is_read = False
            notification.save(update_fields=["is_read"])
    else:
        notification = Notification.objects.create(**lookup)

    payload = NotificationReadSerializer(notification, context={}).data
    unread_count = Notification.objects.filter(recipient=recipient, is_read=False).count()
    broadcast_notification_event(
        recipient.id,
        {
            "event": "notification_created",
            "notification": payload,
            "unread_count": unread_count,
        },
    )
    return notification


def social_post_notification_recipient_ids(post):
    if post.visibility == Post.VISIBILITY_PRIVATE:
        return set()

    blocked_rows = Block.objects.filter(
        Q(blocker_id=post.author_id) | Q(blocked_id=post.author_id)
    ).values_list("blocker_id", "blocked_id")
    blocked_user_ids = set()
    for blocker_id, blocked_id in blocked_rows:
        if blocker_id == post.author_id:
            blocked_user_ids.add(blocked_id)
        if blocked_id == post.author_id:
            blocked_user_ids.add(blocker_id)

    follower_ids = set(
        Follow.objects.filter(following_id=post.author_id).values_list("follower_id", flat=True)
    )
    if post.visibility == Post.VISIBILITY_FOLLOWERS_ONLY:
        recipients = follower_ids
    else:
        friend_rows = FriendRequest.objects.filter(
            status=FriendRequest.STATUS_ACCEPTED,
        ).filter(
            Q(from_user_id=post.author_id) | Q(to_user_id=post.author_id)
        ).values_list("from_user_id", "to_user_id")
        friend_ids = set()
        for from_user_id, to_user_id in friend_rows:
            friend_ids.add(to_user_id if from_user_id == post.author_id else from_user_id)
        recipients = follower_ids | friend_ids

    recipients.discard(post.author_id)
    return recipients - blocked_user_ids


def create_new_post_notifications(post):
    recipient_ids = social_post_notification_recipient_ids(post)
    if not recipient_ids:
        return 0

    created_count = 0
    from django.contrib.auth import get_user_model

    User = get_user_model()
    recipients = User.objects.filter(id__in=recipient_ids)
    for recipient in recipients:
        notification = create_notification_if_applicable(
            recipient=recipient,
            actor=post.author,
            notification_type=Notification.TYPE_NEW_POST,
            target_post=post,
            dedupe=True,
        )
        if notification:
            created_count += 1
    return created_count
