from django.contrib import admin
from .models import Profile, Follow, Post, PostMedia, PostLike, Comment

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
