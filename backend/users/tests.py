from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Block, Follow, FriendRequest, Notification, Post, PostLike, Comment, Report
from .social_realtime import recipient_user_ids_for_post

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

    def test_feed_former_follower_cannot_see_followers_only_after_unfollow(self):
        Follow.objects.create(follower=self.bob, following=self.alice)
        followers_only_post = Post.objects.create(
            author=self.alice,
            content="Temporary followers only",
            visibility=Post.VISIBILITY_FOLLOWERS_ONLY,
        )
        initial_feed_ids = self._feed_post_ids(self.bob)
        self.assertIn(followers_only_post.id, initial_feed_ids)

        Follow.objects.filter(follower=self.bob, following=self.alice).delete()
        feed_ids_after_unfollow = self._feed_post_ids(self.bob)
        self.assertNotIn(followers_only_post.id, feed_ids_after_unfollow)

    def test_feed_author_always_sees_own_followers_only_post(self):
        post = Post.objects.create(
            author=self.alice,
            content="Author should see this",
            visibility=Post.VISIBILITY_FOLLOWERS_ONLY,
        )
        author_feed_ids = self._feed_post_ids(self.alice)
        self.assertIn(post.id, author_feed_ids)

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

    def test_like_state_is_per_authenticated_user(self):
        post = Post.objects.create(author=self.alice, content="Per-user like state", visibility=Post.VISIBILITY_PUBLIC)
        PostLike.objects.create(user=self.alice, post=post)

        self._auth(self.alice)
        response_alice = self.client.get("/api/social/feed/")
        self.assertEqual(response_alice.status_code, status.HTTP_200_OK)
        alice_post = next(item for item in self._results(response_alice) if item["id"] == post.id)
        self.assertTrue(alice_post["is_liked_by_me"])

        self._auth(self.bob)
        response_bob = self.client.get("/api/social/feed/")
        self.assertEqual(response_bob.status_code, status.HTTP_200_OK)
        bob_post = next(item for item in self._results(response_bob) if item["id"] == post.id)
        self.assertFalse(bob_post["is_liked_by_me"])
        self.assertEqual(bob_post["like_count"], 1)

    def test_two_users_can_like_same_post_and_like_count_is_correct(self):
        post = Post.objects.create(author=self.alice, content="Many likes", visibility=Post.VISIBILITY_PUBLIC)

        self._auth(self.alice)
        like_alice = self.client.post(f"/api/social/posts/{post.id}/like/", {}, format="json")
        self.assertEqual(like_alice.status_code, status.HTTP_201_CREATED)

        self._auth(self.bob)
        like_bob = self.client.post(f"/api/social/posts/{post.id}/like/", {}, format="json")
        self.assertEqual(like_bob.status_code, status.HTTP_201_CREATED)

        self.assertEqual(PostLike.objects.filter(post=post).count(), 2)
        response = self.client.get("/api/social/feed/")
        post_payload = next(item for item in self._results(response) if item["id"] == post.id)
        self.assertEqual(post_payload["like_count"], 2)
        self.assertTrue(post_payload["is_liked_by_me"])

    def test_unlike_by_one_user_does_not_remove_other_users_like(self):
        post = Post.objects.create(author=self.alice, content="Unlike isolation", visibility=Post.VISIBILITY_PUBLIC)
        PostLike.objects.create(user=self.alice, post=post)
        PostLike.objects.create(user=self.bob, post=post)

        self._auth(self.alice)
        unlike_response = self.client.post(f"/api/social/posts/{post.id}/unlike/", {}, format="json")
        self.assertEqual(unlike_response.status_code, status.HTTP_200_OK)

        self.assertFalse(PostLike.objects.filter(user=self.alice, post=post).exists())
        self.assertTrue(PostLike.objects.filter(user=self.bob, post=post).exists())
        self.assertEqual(PostLike.objects.filter(post=post).count(), 1)

    def test_post_detail_serializer_like_state_differs_per_user(self):
        post = Post.objects.create(author=self.alice, content="Detail like state", visibility=Post.VISIBILITY_PUBLIC)
        PostLike.objects.create(user=self.alice, post=post)

        self._auth(self.alice)
        detail_alice = self.client.get(f"/api/social/posts/{post.id}/")
        self.assertEqual(detail_alice.status_code, status.HTTP_200_OK)
        self.assertTrue(detail_alice.data["is_liked_by_me"])
        self.assertEqual(detail_alice.data["like_count"], 1)

        self._auth(self.charlie)
        detail_charlie = self.client.get(f"/api/social/posts/{post.id}/")
        self.assertEqual(detail_charlie.status_code, status.HTTP_200_OK)
        self.assertFalse(detail_charlie.data["is_liked_by_me"])
        self.assertEqual(detail_charlie.data["like_count"], 1)

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


class AuthRefreshSafetyTests(APITestCase):
    def test_refresh_with_deleted_user_returns_auth_error_not_server_error(self):
        user = User.objects.create_user(username="temp_refresh", password="pass12345")
        refresh = str(RefreshToken.for_user(user))
        user.delete()

        response = self.client.post("/api/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertIn(response.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED))


class SocialRealtimeAudienceTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice_rt", password="pass12345")
        self.bob = User.objects.create_user(username="bob_rt", password="pass12345")
        self.charlie = User.objects.create_user(username="charlie_rt", password="pass12345")
        Follow.objects.create(follower=self.bob, following=self.alice)

    def test_public_post_recipient_ids_include_visible_users(self):
        post = Post.objects.create(
            author=self.alice,
            content="Public realtime test",
            visibility=Post.VISIBILITY_PUBLIC,
        )
        recipients = recipient_user_ids_for_post(post)
        self.assertEqual(recipients, {self.alice.id, self.bob.id, self.charlie.id})

    def test_followers_only_recipient_ids_include_author_and_followers(self):
        post = Post.objects.create(
            author=self.alice,
            content="Followers-only realtime test",
            visibility=Post.VISIBILITY_FOLLOWERS_ONLY,
        )
        recipients = recipient_user_ids_for_post(post)
        self.assertEqual(recipients, {self.alice.id, self.bob.id})
        self.assertNotIn(self.charlie.id, recipients)

    def test_private_post_recipient_ids_include_only_author(self):
        post = Post.objects.create(
            author=self.alice,
            content="Private realtime test",
            visibility=Post.VISIBILITY_PRIVATE,
        )
        recipients = recipient_user_ids_for_post(post)
        self.assertEqual(recipients, {self.alice.id})


class SocialNotificationAndSafetyTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice_ns", password="pass12345")
        self.bob = User.objects.create_user(username="bob_ns", password="pass12345")
        self.charlie = User.objects.create_user(username="charlie_ns", password="pass12345")

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _unread_count(self, user):
        self._auth(user)
        response = self.client.get("/api/social/notifications/unread-count/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return int(response.data.get("unread_count", 0))

    def test_follow_creates_notification(self):
        self._auth(self.bob)
        response = self.client.post(f"/api/social/profiles/{self.alice.id}/follow/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notif = Notification.objects.filter(recipient=self.alice, actor=self.bob, type=Notification.TYPE_FOLLOW).first()
        self.assertIsNotNone(notif)

    def test_like_creates_notification(self):
        post = Post.objects.create(author=self.alice, content="Like me", visibility=Post.VISIBILITY_PUBLIC)
        self._auth(self.bob)
        response = self.client.post(f"/api/social/posts/{post.id}/like/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notif = Notification.objects.filter(
            recipient=self.alice,
            actor=self.bob,
            type=Notification.TYPE_POST_LIKE,
            target_post=post,
        ).first()
        self.assertIsNotNone(notif)

    def test_comment_creates_notification(self):
        post = Post.objects.create(author=self.alice, content="Comment me", visibility=Post.VISIBILITY_PUBLIC)
        self._auth(self.bob)
        response = self.client.post(
            f"/api/social/posts/{post.id}/comments/",
            {"content": "Hi"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notif = Notification.objects.filter(
            recipient=self.alice,
            actor=self.bob,
            type=Notification.TYPE_POST_COMMENT,
            target_post=post,
        ).first()
        self.assertIsNotNone(notif)

    def test_self_notification_is_not_created(self):
        post = Post.objects.create(author=self.alice, content="Own post", visibility=Post.VISIBILITY_PUBLIC)
        self._auth(self.alice)
        response = self.client.post(f"/api/social/posts/{post.id}/like/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Notification.objects.filter(recipient=self.alice).exists())

    def test_block_prevents_follow(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self._auth(self.bob)
        response = self.client.post(f"/api/social/profiles/{self.alice.id}/follow/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Follow.objects.filter(follower=self.bob, following=self.alice).exists())

    def test_block_prevents_like_and_comment(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        post = Post.objects.create(author=self.alice, content="Blocked post", visibility=Post.VISIBILITY_PUBLIC)
        self._auth(self.bob)
        like_resp = self.client.post(f"/api/social/posts/{post.id}/like/", {}, format="json")
        comment_resp = self.client.post(
            f"/api/social/posts/{post.id}/comments/",
            {"content": "Should not work"},
            format="json",
        )
        self.assertIn(like_resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.assertIn(comment_resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.assertFalse(PostLike.objects.filter(user=self.bob, post=post).exists())
        self.assertFalse(Comment.objects.filter(author=self.bob, post=post).exists())

    def test_block_hides_posts_from_feed(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        post = Post.objects.create(author=self.alice, content="Hidden post", visibility=Post.VISIBILITY_PUBLIC)
        self._auth(self.bob)
        response = self.client.get("/api/social/feed/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(post.id, ids)

    def test_report_endpoints_create_reports(self):
        post = Post.objects.create(author=self.alice, content="Reportable", visibility=Post.VISIBILITY_PUBLIC)
        self._auth(self.bob)
        report_user = self.client.post(
            f"/api/social/reports/users/{self.alice.id}/",
            {"reason": "abuse", "details": "spam profile"},
            format="json",
        )
        report_post = self.client.post(
            f"/api/social/reports/posts/{post.id}/",
            {"reason": "spam", "details": "spam post"},
            format="json",
        )
        self.assertEqual(report_user.status_code, status.HTTP_201_CREATED)
        self.assertEqual(report_post.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Report.objects.filter(reporter=self.bob).count(), 2)

    def test_notifications_list_returns_only_current_user_notifications(self):
        Notification.objects.create(recipient=self.alice, actor=self.bob, type=Notification.TYPE_FOLLOW)
        Notification.objects.create(recipient=self.bob, actor=self.alice, type=Notification.TYPE_FOLLOW)
        self._auth(self.alice)
        response = self.client.get("/api/social/notifications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["actor"]["id"], self.bob.id)

    def test_mark_one_notification_as_read(self):
        notif = Notification.objects.create(recipient=self.alice, actor=self.bob, type=Notification.TYPE_FOLLOW)
        Notification.objects.create(recipient=self.alice, actor=self.charlie, type=Notification.TYPE_FOLLOW)
        self.assertEqual(self._unread_count(self.alice), 2)
        self._auth(self.alice)
        response = self.client.post(f"/api/social/notifications/{notif.id}/read/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertEqual(self._unread_count(self.alice), 1)

    def test_mark_all_notifications_as_read(self):
        Notification.objects.create(recipient=self.alice, actor=self.bob, type=Notification.TYPE_FOLLOW)
        Notification.objects.create(recipient=self.alice, actor=self.charlie, type=Notification.TYPE_FOLLOW)
        self.assertEqual(self._unread_count(self.alice), 2)
        self._auth(self.alice)
        response = self.client.post("/api/social/notifications/read-all/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Notification.objects.filter(recipient=self.alice, is_read=True).count(), 2)
        self.assertEqual(self._unread_count(self.alice), 0)

    def test_unread_notification_count_is_correct(self):
        Notification.objects.create(recipient=self.alice, actor=self.bob, type=Notification.TYPE_FOLLOW, is_read=False)
        Notification.objects.create(recipient=self.alice, actor=self.charlie, type=Notification.TYPE_FOLLOW, is_read=True)
        self.assertEqual(self._unread_count(self.alice), 1)

    def test_follow_like_comment_update_unread_count(self):
        post = Post.objects.create(author=self.alice, content="Track counts", visibility=Post.VISIBILITY_PUBLIC)

        self._auth(self.bob)
        follow_response = self.client.post(f"/api/social/profiles/{self.alice.id}/follow/", {}, format="json")
        self.assertEqual(follow_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self._unread_count(self.alice), 1)

        self._auth(self.bob)
        like_response = self.client.post(f"/api/social/posts/{post.id}/like/", {}, format="json")
        self.assertEqual(like_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self._unread_count(self.alice), 2)

        self._auth(self.charlie)
        comment_response = self.client.post(
            f"/api/social/posts/{post.id}/comments/",
            {"content": "counting"},
            format="json",
        )
        self.assertEqual(comment_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self._unread_count(self.alice), 3)

    def test_users_directory_includes_block_state_flags(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self._auth(self.alice)
        response = self.client.get("/api/auth/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bob_entry = next((u for u in response.data if u["id"] == self.bob.id), None)
        self.assertIsNotNone(bob_entry)
        self.assertTrue(bob_entry["is_blocked_by_me"])
        self.assertFalse(bob_entry["has_blocked_me"])
        self.assertEqual(bob_entry["friend_status"], "blocked")

    def test_blocked_user_discoverable_and_unblockable_without_profile(self):
        self._auth(self.alice)
        block_response = self.client.post(f"/api/social/blocks/{self.bob.id}/", {}, format="json")
        self.assertEqual(block_response.status_code, status.HTTP_201_CREATED)

        directory_before = self.client.get("/api/auth/users/")
        self.assertEqual(directory_before.status_code, status.HTTP_200_OK)
        bob_entry_before = next((u for u in directory_before.data if u["id"] == self.bob.id), None)
        self.assertIsNotNone(bob_entry_before)
        self.assertTrue(bob_entry_before["is_blocked_by_me"])

        unblock_response = self.client.delete(f"/api/social/blocks/{self.bob.id}/")
        self.assertEqual(unblock_response.status_code, status.HTTP_204_NO_CONTENT)

        directory_after = self.client.get("/api/auth/users/")
        self.assertEqual(directory_after.status_code, status.HTTP_200_OK)
        bob_entry_after = next((u for u in directory_after.data if u["id"] == self.bob.id), None)
        self.assertIsNotNone(bob_entry_after)
        self.assertFalse(bob_entry_after["is_blocked_by_me"])

    def test_blocked_user_not_reported_as_normal_connected_or_followable(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        FriendRequest.objects.create(from_user=self.alice, to_user=self.bob, status=FriendRequest.STATUS_ACCEPTED)
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        self._auth(self.alice)
        response = self.client.get("/api/auth/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bob_entry = next((u for u in response.data if u["id"] == self.bob.id), None)
        self.assertIsNotNone(bob_entry)
        self.assertEqual(bob_entry["friend_status"], "blocked")
        self.assertFalse(bob_entry["is_following"])
