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

    def _feed_post_ids(self, user):
        self._auth(user)
        response = self.client.get("/api/social/feed/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [item["id"] for item in self._results(response)]

    def _profile_post_ids(self, viewer, target_user):
        self._auth(viewer)
        response = self.client.get(f"/api/social/profiles/{target_user.id}/posts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [item["id"] for item in self._results(response)]

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

    def test_feed_non_follower_sees_public_post(self):
        public_post = Post.objects.create(
            author=self.alice,
            content="Visible to everyone",
            visibility=Post.VISIBILITY_PUBLIC,
        )
        feed_ids = self._feed_post_ids(self.charlie)
        self.assertIn(public_post.id, feed_ids)

    def test_feed_non_follower_cannot_see_followers_only_post(self):
        followers_only_post = Post.objects.create(
            author=self.alice,
            content="Followers only",
            visibility=Post.VISIBILITY_FOLLOWERS_ONLY,
        )
        feed_ids = self._feed_post_ids(self.charlie)
        self.assertNotIn(followers_only_post.id, feed_ids)

    def test_feed_follower_can_see_followers_only_post(self):
        Follow.objects.create(follower=self.bob, following=self.alice)
        followers_only_post = Post.objects.create(
            author=self.alice,
            content="Followers can read this",
            visibility=Post.VISIBILITY_FOLLOWERS_ONLY,
        )
        feed_ids = self._feed_post_ids(self.bob)
        self.assertIn(followers_only_post.id, feed_ids)

    def test_feed_private_post_visible_only_to_author(self):
        private_post = Post.objects.create(
            author=self.alice,
            content="Private note",
            visibility=Post.VISIBILITY_PRIVATE,
        )
        author_feed_ids = self._feed_post_ids(self.alice)
        non_author_feed_ids = self._feed_post_ids(self.bob)
        self.assertIn(private_post.id, author_feed_ids)
        self.assertNotIn(private_post.id, non_author_feed_ids)

    def test_feed_has_no_duplicate_posts(self):
        Follow.objects.create(follower=self.bob, following=self.alice)
        public_post = Post.objects.create(
            author=self.alice,
            content="Public should appear once",
            visibility=Post.VISIBILITY_PUBLIC,
        )
        Post.objects.create(
            author=self.bob,
            content="Bob post",
            visibility=Post.VISIBILITY_PUBLIC,
        )
        feed_ids = self._feed_post_ids(self.bob)
        self.assertEqual(len(feed_ids), len(set(feed_ids)))
        self.assertEqual(feed_ids.count(public_post.id), 1)

    def test_profile_posts_visibility_rules(self):
        public_post = Post.objects.create(
            author=self.alice,
            content="Public profile post",
            visibility=Post.VISIBILITY_PUBLIC,
        )
        followers_post = Post.objects.create(
            author=self.alice,
            content="Followers profile post",
            visibility=Post.VISIBILITY_FOLLOWERS_ONLY,
        )
        private_post = Post.objects.create(
            author=self.alice,
            content="Private profile post",
            visibility=Post.VISIBILITY_PRIVATE,
        )
        Follow.objects.create(follower=self.bob, following=self.alice)

        owner_ids = self._profile_post_ids(self.alice, self.alice)
        follower_ids = self._profile_post_ids(self.bob, self.alice)
        non_follower_ids = self._profile_post_ids(self.charlie, self.alice)

        self.assertIn(public_post.id, owner_ids)
        self.assertIn(followers_post.id, owner_ids)
        self.assertIn(private_post.id, owner_ids)

        self.assertIn(public_post.id, follower_ids)
        self.assertIn(followers_post.id, follower_ids)
        self.assertNotIn(private_post.id, follower_ids)

        self.assertIn(public_post.id, non_follower_ids)
        self.assertNotIn(followers_post.id, non_follower_ids)
        self.assertNotIn(private_post.id, non_follower_ids)

    def test_users_directory_includes_is_following(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self._auth(self.alice)
        response = self.client.get("/api/auth/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data
        bob_entry = next((u for u in payload if u["id"] == self.bob.id), None)
        charlie_entry = next((u for u in payload if u["id"] == self.charlie.id), None)
        self.assertIsNotNone(bob_entry)
        self.assertIsNotNone(charlie_entry)
        self.assertIn("is_following", bob_entry)
        self.assertTrue(bob_entry["is_following"])
        self.assertFalse(charlie_entry["is_following"])

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
