from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Follow, Post, PostLike, Comment

User = get_user_model()


class SocialLayerAPITests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pass12345")
        self.bob = User.objects.create_user(username="bob", password="pass12345")
        self.charlie = User.objects.create_user(username="charlie", password="pass12345")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _results(self, response):
        if isinstance(response.data, dict) and "results" in response.data:
            return response.data["results"]
        return response.data

    def test_self_follow_blocked(self):
        self._auth(self.alice)
        url = f"/api/social/profiles/{self.alice.id}/follow/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Follow.objects.count(), 0)

    def test_duplicate_follow_blocked(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self._auth(self.alice)
        url = f"/api/social/profiles/{self.bob.id}/follow/"
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Follow.objects.filter(follower=self.alice, following=self.bob).count(), 1)

    def test_create_post(self):
        self._auth(self.alice)
        response = self.client.post(
            "/api/social/feed/",
            {"content": "My first social post", "visibility": "public"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Post.objects.count(), 1)
        self.assertEqual(response.data["content"], "My first social post")
        self.assertIn("like_count", response.data)
        self.assertIn("comment_count", response.data)
        self.assertIn("is_liked_by_me", response.data)

    def test_followers_only_visibility(self):
        post = Post.objects.create(
            author=self.alice,
            content="Followers-only",
            visibility=Post.VISIBILITY_FOLLOWERS_ONLY,
        )
        Follow.objects.create(follower=self.bob, following=self.alice)

        self._auth(self.bob)
        response_follower = self.client.get(f"/api/social/profiles/{self.alice.id}/posts/")
        self.assertEqual(response_follower.status_code, status.HTTP_200_OK)
        follower_results = self._results(response_follower)
        self.assertTrue(any(item["id"] == post.id for item in follower_results))

        self._auth(self.charlie)
        response_non_follower = self.client.get(f"/api/social/profiles/{self.alice.id}/posts/")
        self.assertEqual(response_non_follower.status_code, status.HTTP_200_OK)
        non_follower_results = self._results(response_non_follower)
        self.assertFalse(any(item["id"] == post.id for item in non_follower_results))

    def test_like_uniqueness(self):
        post = Post.objects.create(author=self.alice, content="Public post", visibility=Post.VISIBILITY_PUBLIC)
        self._auth(self.bob)

        like_url = f"/api/social/posts/{post.id}/like/"
        first = self.client.post(like_url, {}, format="json")
        second = self.client.post(like_url, {}, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PostLike.objects.filter(post=post, user=self.bob).count(), 1)

    def test_comment_create_edit_delete_permissions(self):
        post = Post.objects.create(author=self.alice, content="Commentable", visibility=Post.VISIBILITY_PUBLIC)

        self._auth(self.bob)
        create_resp = self.client.post(
            f"/api/social/posts/{post.id}/comments/",
            {"content": "Nice post"},
            format="json",
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        comment_id = create_resp.data["id"]
        self.assertEqual(Comment.objects.count(), 1)

        self._auth(self.charlie)
        outsider_patch = self.client.patch(
            f"/api/social/comments/{comment_id}/",
            {"content": "I should not edit this"},
            format="json",
        )
        outsider_delete = self.client.delete(f"/api/social/comments/{comment_id}/")
        self.assertEqual(outsider_patch.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(outsider_delete.status_code, status.HTTP_403_FORBIDDEN)

        self._auth(self.bob)
        owner_patch = self.client.patch(
            f"/api/social/comments/{comment_id}/",
            {"content": "Edited by owner"},
            format="json",
        )
        owner_delete = self.client.delete(f"/api/social/comments/{comment_id}/")
        self.assertEqual(owner_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(owner_delete.status_code, status.HTTP_204_NO_CONTENT)

        updated = Comment.objects.get(pk=comment_id)
        self.assertTrue(updated.is_deleted)
