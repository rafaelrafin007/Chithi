from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Block, Follow, Post, PostMedia, PostLike, Comment, Notification, Report, is_blocked_between
from .pagination import StandardPagination
from .permissions import IsPostOwnerOrReadOnly, IsCommentOwnerOrReadOnly
from .serializers import UserSimpleSerializer
from .social_serializers import (
    PublicProfileSerializer,
    PostReadSerializer,
    PostWriteSerializer,
    CommentReadSerializer,
    CommentWriteSerializer,
    NotificationReadSerializer,
    ReportWriteSerializer,
    BlockReadSerializer,
)
from .social_realtime import (
    broadcast_event_for_post,
    comment_count_for_post,
    like_count_for_post,
    post_update_payload,
    serialize_comment_for_realtime,
    serialize_post_for_realtime,
)

User = get_user_model()


def _get_user_by_identifier(identifier):
    if str(identifier).isdigit():
        return get_object_or_404(User.objects.select_related("profile"), pk=int(identifier))
    return get_object_or_404(User.objects.select_related("profile"), username=identifier)


def _annotated_posts_queryset(user, queryset):
    if user and user.is_authenticated:
        liked_by_me_qs = PostLike.objects.filter(post=OuterRef("pk"), user_id=user.id)
    else:
        liked_by_me_qs = PostLike.objects.none()
    return (
        queryset.select_related("author", "author__profile")
        .prefetch_related("media")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", filter=Q(comments__is_deleted=False), distinct=True),
            is_liked_by_me=Exists(liked_by_me_qs),
        )
        .order_by("-created_at")
    )


def _is_blocked_between_users(user_a, user_b):
    return is_blocked_between(user_a, user_b)


def _create_notification_if_applicable(recipient, actor, notification_type, target_post=None, target_comment=None):
    if not recipient or not actor:
        return
    if recipient.id == actor.id:
        return
    Notification.objects.create(
        recipient=recipient,
        actor=actor,
        type=notification_type,
        target_post=target_post,
        target_comment=target_comment,
    )


def _visible_posts_queryset_for_user(user):
    follow_exists = Follow.objects.filter(follower=user, following=OuterRef("author_id"))
    blocked_exists = Block.objects.filter(
        Q(blocker=user, blocked=OuterRef("author_id")) | Q(blocked=user, blocker=OuterRef("author_id"))
    )
    base = Post.objects.filter(is_deleted=False).annotate(
        _follows_author=Exists(follow_exists),
        _is_blocked_author=Exists(blocked_exists),
    )
    return base.filter(
        _is_blocked_author=False
    ).filter(
        Q(author=user)
        | Q(visibility=Post.VISIBILITY_PUBLIC)
        | Q(visibility=Post.VISIBILITY_FOLLOWERS_ONLY, _follows_author=True)
    )


def _get_visible_post_or_404(user, post_id):
    queryset = _annotated_posts_queryset(user, _visible_posts_queryset_for_user(user))
    return get_object_or_404(queryset, pk=post_id)


class PublicProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, identifier):
        following_exists = Follow.objects.filter(follower=request.user, following=OuterRef("pk"))
        blocked_by_me_exists = Block.objects.filter(blocker=request.user, blocked=OuterRef("pk"))
        has_blocked_me_exists = Block.objects.filter(blocker=OuterRef("pk"), blocked=request.user)
        base_queryset = User.objects.select_related("profile").annotate(
            followers_count=Count("follower_relations", distinct=True),
            following_count=Count("following_relations", distinct=True),
            posts_count=Count("posts", filter=Q(posts__is_deleted=False), distinct=True),
            is_following=Exists(following_exists),
            is_blocked_by_me=Exists(blocked_by_me_exists),
            has_blocked_me=Exists(has_blocked_me_exists),
        )
        if str(identifier).isdigit():
            target = base_queryset.filter(pk=int(identifier)).first()
        else:
            target = base_queryset.filter(username=identifier).first()
        if not target:
            return Response({"detail": "User not found"}, status=404)
        data = PublicProfileSerializer(target, context={"request": request}).data
        return Response(data)


class FollowUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, identifier):
        target = _get_user_by_identifier(identifier)
        if target.id == request.user.id:
            return Response({"detail": "You cannot follow yourself."}, status=400)
        if _is_blocked_between_users(request.user, target):
            return Response({"detail": "Follow is not allowed because one user has blocked the other."}, status=403)
        try:
            Follow.objects.create(follower=request.user, following=target)
        except DjangoValidationError as exc:
            return Response({"detail": exc.message_dict if hasattr(exc, "message_dict") else str(exc)}, status=400)
        except IntegrityError:
            return Response({"detail": "You already follow this user."}, status=400)
        _create_notification_if_applicable(
            recipient=target,
            actor=request.user,
            notification_type=Notification.TYPE_FOLLOW,
        )
        return Response({"detail": "Followed successfully."}, status=201)


class UnfollowUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, identifier):
        target = _get_user_by_identifier(identifier)
        deleted, _ = Follow.objects.filter(follower=request.user, following=target).delete()
        if not deleted:
            return Response({"detail": "You do not follow this user."}, status=400)
        return Response({"detail": "Unfollowed successfully."}, status=200)


class FollowersListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request, identifier):
        target = _get_user_by_identifier(identifier)
        if _is_blocked_between_users(request.user, target):
            return Response({"detail": "Followers are unavailable for blocked users."}, status=403)
        users = User.objects.filter(following_relations__following=target).select_related("profile").order_by(
            "-following_relations__created_at"
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(users, request, view=self)
        serialized = UserSimpleSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(serialized)


class FollowingListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request, identifier):
        target = _get_user_by_identifier(identifier)
        if _is_blocked_between_users(request.user, target):
            return Response({"detail": "Following list is unavailable for blocked users."}, status=403)
        users = User.objects.filter(follower_relations__follower=target).select_related("profile").order_by(
            "-follower_relations__created_at"
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(users, request, view=self)
        serialized = UserSimpleSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(serialized)


class FeedView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    pagination_class = StandardPagination

    def get(self, request):
        queryset = _visible_posts_queryset_for_user(request.user)
        queryset = _annotated_posts_queryset(request.user, queryset)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serialized = PostReadSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(serialized)

    def post(self, request):
        uploaded_files = request.FILES.getlist("media")
        if not uploaded_files:
            single = request.FILES.get("image") or request.FILES.get("file")
            if single:
                uploaded_files = [single]

        serializer = PostWriteSerializer(
            data=request.data,
            context={"request": request, "uploaded_files": uploaded_files},
        )
        serializer.is_valid(raise_exception=True)

        for f in uploaded_files:
            content_type = (getattr(f, "content_type", "") or "").lower()
            if not content_type.startswith("image/"):
                return Response({"detail": "Only image uploads are supported for posts."}, status=400)

        with transaction.atomic():
            post = Post.objects.create(
                author=request.user,
                content=serializer.validated_data.get("content", ""),
                visibility=serializer.validated_data.get("visibility", Post.VISIBILITY_PUBLIC),
            )
            for f in uploaded_files:
                PostMedia.objects.create(post=post, file=f, media_type=PostMedia.MEDIA_TYPE_IMAGE)

        post = _annotated_posts_queryset(request.user, Post.objects.filter(pk=post.pk)).first()
        data = PostReadSerializer(post, context={"request": request}).data

        transaction.on_commit(
            lambda: broadcast_event_for_post(
                post,
                {
                    "event": "post_created",
                    "actor_id": request.user.id,
                    "post_id": post.id,
                    "post": serialize_post_for_realtime(post, request=request),
                },
            )
        )
        return Response(data, status=201)


class ProfilePostsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request, identifier):
        target = _get_user_by_identifier(identifier)
        if _is_blocked_between_users(request.user, target):
            return Response({"detail": "Posts are unavailable for blocked users."}, status=403)
        queryset = _visible_posts_queryset_for_user(request.user).filter(author=target)

        queryset = _annotated_posts_queryset(request.user, queryset)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serialized = PostReadSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(serialized)


class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsPostOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    lookup_url_kwarg = "post_id"

    def get_queryset(self):
        visible = _visible_posts_queryset_for_user(self.request.user)
        return _annotated_posts_queryset(self.request.user, visible)

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return PostWriteSerializer
        return PostReadSerializer

    def patch(self, request, *args, **kwargs):
        post = self.get_object()
        self.check_object_permissions(request, post)

        serializer = PostWriteSerializer(
            post,
            data=request.data,
            partial=True,
            context={"request": request, "uploaded_files": []},
        )
        serializer.is_valid(raise_exception=True)

        old_content = post.content
        post.content = serializer.validated_data.get("content", post.content)
        post.visibility = serializer.validated_data.get("visibility", post.visibility)
        if post.content != old_content:
            post.is_edited = True
        post.save(update_fields=["content", "visibility", "is_edited", "updated_at"])

        post = _annotated_posts_queryset(request.user, Post.objects.filter(pk=post.pk)).first()
        data = PostReadSerializer(post, context={"request": request}).data

        transaction.on_commit(
            lambda: broadcast_event_for_post(
                post,
                {
                    "event": "post_updated",
                    "actor_id": request.user.id,
                    "post_id": post.id,
                    "post": post_update_payload(post, request=request),
                },
            )
        )
        return Response(data)

    def delete(self, request, *args, **kwargs):
        post = self.get_object()
        self.check_object_permissions(request, post)
        post.is_deleted = True
        post.save(update_fields=["is_deleted", "updated_at"])
        transaction.on_commit(
            lambda: broadcast_event_for_post(
                post,
                {
                    "event": "post_deleted",
                    "actor_id": request.user.id,
                    "post_id": post.id,
                },
            )
        )
        return Response(status=204)


class LikePostView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, post_id):
        post = _get_visible_post_or_404(request.user, post_id)
        if _is_blocked_between_users(request.user, post.author):
            return Response({"detail": "You cannot like posts from blocked users."}, status=403)
        try:
            with transaction.atomic():
                PostLike.objects.create(user=request.user, post=post)
        except IntegrityError:
            return Response({"detail": "Post already liked."}, status=400)

        def _after_like():
            broadcast_event_for_post(
                post,
                {
                    "event": "post_liked",
                    "actor_id": request.user.id,
                    "post_id": post.id,
                    "like_count": like_count_for_post(post.id),
                },
            )

        transaction.on_commit(_after_like)
        _create_notification_if_applicable(
            recipient=post.author,
            actor=request.user,
            notification_type=Notification.TYPE_POST_LIKE,
            target_post=post,
        )
        return Response({"detail": "Post liked."}, status=201)


class UnlikePostView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, post_id):
        post = _get_visible_post_or_404(request.user, post_id)
        deleted, _ = PostLike.objects.filter(user=request.user, post=post).delete()
        if not deleted:
            return Response({"detail": "Post is not liked yet."}, status=400)
        transaction.on_commit(
            lambda: broadcast_event_for_post(
                post,
                {
                    "event": "post_unliked",
                    "actor_id": request.user.id,
                    "post_id": post.id,
                    "like_count": like_count_for_post(post.id),
                },
            )
        )
        return Response({"detail": "Post unliked."}, status=200)


class CommentListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    pagination_class = StandardPagination

    def get(self, request, post_id):
        post = _get_visible_post_or_404(request.user, post_id)
        queryset = (
            Comment.objects.filter(post=post)
            .select_related("author", "author__profile", "parent_comment")
            .order_by("created_at")
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serialized = CommentReadSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(serialized)

    def post(self, request, post_id):
        post = _get_visible_post_or_404(request.user, post_id)
        if _is_blocked_between_users(request.user, post.author):
            return Response({"detail": "You cannot comment on posts from blocked users."}, status=403)
        serializer = CommentWriteSerializer(data=request.data, context={"post": post})
        serializer.is_valid(raise_exception=True)
        comment = Comment.objects.create(
            post=post,
            author=request.user,
            content=serializer.validated_data["content"],
            parent_comment=serializer.validated_data.get("parent_comment"),
        )
        data = CommentReadSerializer(comment, context={"request": request}).data

        def _after_comment_create():
            broadcast_event_for_post(
                post,
                {
                    "event": "comment_created",
                    "actor_id": request.user.id,
                    "post_id": post.id,
                    "comment": serialize_comment_for_realtime(comment, request=request),
                    "comment_count": comment_count_for_post(post.id),
                },
            )

        transaction.on_commit(_after_comment_create)
        _create_notification_if_applicable(
            recipient=post.author,
            actor=request.user,
            notification_type=Notification.TYPE_POST_COMMENT,
            target_post=post,
            target_comment=comment,
        )
        return Response(data, status=201)


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsCommentOwnerOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    lookup_url_kwarg = "comment_id"

    def get_queryset(self):
        visible_post_ids = _visible_posts_queryset_for_user(self.request.user).values("id")
        return Comment.objects.filter(post_id__in=Subquery(visible_post_ids)).select_related(
            "author", "author__profile", "post", "parent_comment"
        )

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return CommentWriteSerializer
        return CommentReadSerializer

    def patch(self, request, *args, **kwargs):
        comment = self.get_object()
        self.check_object_permissions(request, comment)
        if comment.is_deleted:
            return Response({"detail": "Deleted comments cannot be edited."}, status=400)

        serializer = CommentWriteSerializer(
            comment,
            data=request.data,
            partial=True,
            context={"post": comment.post},
        )
        serializer.is_valid(raise_exception=True)

        if "content" in serializer.validated_data:
            comment.content = serializer.validated_data["content"]
        if "parent_comment" in serializer.validated_data:
            comment.parent_comment = serializer.validated_data["parent_comment"]
        comment.save(update_fields=["content", "parent_comment", "updated_at"])
        data = CommentReadSerializer(comment, context={"request": request}).data
        transaction.on_commit(
            lambda: broadcast_event_for_post(
                comment.post,
                {
                    "event": "comment_updated",
                    "actor_id": request.user.id,
                    "post_id": comment.post_id,
                    "comment": serialize_comment_for_realtime(comment, request=request),
                    "comment_count": comment_count_for_post(comment.post_id),
                },
            )
        )
        return Response(data)

    def delete(self, request, *args, **kwargs):
        comment = self.get_object()
        self.check_object_permissions(request, comment)
        comment.is_deleted = True
        comment.content = "This comment was deleted"
        comment.save(update_fields=["is_deleted", "content", "updated_at"])
        transaction.on_commit(
            lambda: broadcast_event_for_post(
                comment.post,
                {
                    "event": "comment_deleted",
                    "actor_id": request.user.id,
                    "post_id": comment.post_id,
                    "comment_id": comment.id,
                    "comment": serialize_comment_for_realtime(comment, request=request),
                    "comment_count": comment_count_for_post(comment.post_id),
                },
            )
        )
        return Response(status=204)


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Notification.objects.filter(recipient=request.user).select_related(
            "actor", "actor__profile", "target_post", "target_comment"
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = NotificationReadSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        data = NotificationReadSerializer(notification, context={"request": request}).data
        return Response(data, status=200)


class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({"detail": "All notifications marked as read."}, status=200)


class BlockListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Block.objects.filter(blocker=request.user).select_related("blocked", "blocked__profile")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = BlockReadSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)


class BlockUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, identifier):
        target = _get_user_by_identifier(identifier)
        if target.id == request.user.id:
            return Response({"detail": "You cannot block yourself."}, status=400)
        try:
            with transaction.atomic():
                Block.objects.create(blocker=request.user, blocked=target)
                Follow.objects.filter(
                    Q(follower=request.user, following=target) | Q(follower=target, following=request.user)
                ).delete()
        except IntegrityError:
            return Response({"detail": "User is already blocked."}, status=400)
        return Response({"detail": "User blocked."}, status=201)

    def delete(self, request, identifier):
        target = _get_user_by_identifier(identifier)
        deleted, _ = Block.objects.filter(blocker=request.user, blocked=target).delete()
        if not deleted:
            return Response({"detail": "User is not blocked."}, status=400)
        return Response(status=204)


class ReportUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, identifier):
        target = _get_user_by_identifier(identifier)
        if target.id == request.user.id:
            return Response({"detail": "You cannot report yourself."}, status=400)
        serializer = ReportWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = Report.objects.create(
            reporter=request.user,
            target_user=target,
            reason=serializer.validated_data["reason"],
            details=serializer.validated_data.get("details", ""),
        )
        return Response({"id": report.id, "detail": "Report submitted."}, status=201)


class ReportPostView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, post_id):
        post = get_object_or_404(Post, pk=post_id, is_deleted=False)
        serializer = ReportWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = Report.objects.create(
            reporter=request.user,
            target_post=post,
            reason=serializer.validated_data["reason"],
            details=serializer.validated_data.get("details", ""),
        )
        return Response({"id": report.id, "detail": "Report submitted."}, status=201)
