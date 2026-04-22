from django.contrib import admin
from .models import Profile, Follow, Post, PostMedia, PostLike, Comment, Notification, Block, Report

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "phone", "created_at")
    search_fields = ("user__username", "display_name", "phone")


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "created_at")
    search_fields = ("follower__username", "following__username")
    list_select_related = ("follower", "following")


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "visibility", "is_edited", "is_deleted", "created_at")
    list_filter = ("visibility", "is_deleted", "created_at")
    search_fields = ("author__username", "content")
    list_select_related = ("author",)
    inlines = [PostMediaInline]


@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "media_type", "created_at")
    list_filter = ("media_type", "created_at")
    list_select_related = ("post",)


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
    search_fields = ("user__username", "post__id")
    list_select_related = ("user", "post")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("author__username", "content")
    list_select_related = ("post", "author", "parent_comment")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "actor", "type", "is_read", "created_at")
    list_filter = ("type", "is_read", "created_at")
    search_fields = ("recipient__username", "actor__username")
    list_select_related = ("recipient", "actor", "target_post", "target_comment")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__username", "blocked__username")
    list_select_related = ("blocker", "blocked")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "target_user", "target_post", "reason", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("reporter__username", "target_user__username", "reason")
    list_select_related = ("reporter", "target_user", "target_post")
