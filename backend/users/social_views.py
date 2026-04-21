from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Follow, Post, PostMedia, PostLike, Comment
from .pagination import StandardPagination
from .permissions import IsPostOwnerOrReadOnly, IsCommentOwnerOrReadOnly
from .serializers import UserSimpleSerializer
from .social_serializers import (
    PublicProfileSerializer,
    PostReadSerializer,
    PostWriteSerializer,
    CommentReadSerializer,
    CommentWriteSerializer,
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


def _visible_posts_queryset_for_user(user):
    follow_exists = Follow.objects.filter(follower=user, following=OuterRef("author_id"))
    base = Post.objects.filter(is_deleted=False).annotate(_follows_author=Exists(follow_exists))
    return base.filter(
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
        base_queryset = User.objects.select_related("profile").annotate(
            followers_count=Count("follower_relations", distinct=True),
            following_count=Count("following_relations", distinct=True),
            posts_count=Count("posts", filter=Q(posts__is_deleted=False), distinct=True),
            is_following=Exists(following_exists),
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
        try:
            Follow.objects.create(follower=request.user, following=target)
        except DjangoValidationError as exc:
            return Response({"detail": exc.message_dict if hasattr(exc, "message_dict") else str(exc)}, status=400)
        except IntegrityError:
            return Response({"detail": "You already follow this user."}, status=400)
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
        return Response(data, status=201)


class ProfilePostsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request, identifier):
        target = _get_user_by_identifier(identifier)
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
        return Response(data)

    def delete(self, request, *args, **kwargs):
        post = self.get_object()
        self.check_object_permissions(request, post)
        post.is_deleted = True
        post.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=204)


class LikePostView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, post_id):
        post = _get_visible_post_or_404(request.user, post_id)
        try:
            with transaction.atomic():
                PostLike.objects.create(user=request.user, post=post)
        except IntegrityError:
            return Response({"detail": "Post already liked."}, status=400)
        return Response({"detail": "Post liked."}, status=201)


class UnlikePostView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, post_id):
        post = _get_visible_post_or_404(request.user, post_id)
        deleted, _ = PostLike.objects.filter(user=request.user, post=post).delete()
        if not deleted:
            return Response({"detail": "Post is not liked yet."}, status=400)
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
        serializer = CommentWriteSerializer(data=request.data, context={"post": post})
        serializer.is_valid(raise_exception=True)
        comment = Comment.objects.create(
            post=post,
            author=request.user,
            content=serializer.validated_data["content"],
            parent_comment=serializer.validated_data.get("parent_comment"),
        )
        data = CommentReadSerializer(comment, context={"request": request}).data
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
        return Response(data)

    def delete(self, request, *args, **kwargs):
        comment = self.get_object()
        self.check_object_permissions(request, comment)
        comment.is_deleted = True
        comment.content = "This comment was deleted"
        comment.save(update_fields=["is_deleted", "content", "updated_at"])
        return Response(status=204)
