from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import Block, FriendRequest
from .models import ConversationState, Message

User = get_user_model()


class ChatConversationStateTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice_chat", password="pass12345")
        self.bob = User.objects.create_user(username="bob_chat", password="pass12345")
        self.charlie = User.objects.create_user(username="charlie_chat", password="pass12345")

        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _users_payload(self):
        response = self.client.get("/api/chat/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_unread_count_increments_on_new_incoming_message(self):
        self._auth(self.alice)
        send_response = self.client.post(
            "/api/chat/send/",
            {"receiver": self.bob.id, "content": "hi bob"},
            format="json",
        )
        self.assertEqual(send_response.status_code, status.HTTP_201_CREATED)

        self._auth(self.bob)
        users = self._users_payload()
        alice_entry = next((u for u in users if u["id"] == self.alice.id), None)
        self.assertIsNotNone(alice_entry)
        self.assertEqual(alice_entry["unread"], 1)

    def test_legacy_conversation_without_state_appears_in_inbox(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, content="legacy hello")
        self.assertEqual(ConversationState.objects.count(), 0)

        self._auth(self.bob)
        users = self._users_payload()
        alice_entry = next((u for u in users if u["id"] == self.alice.id), None)
        self.assertIsNotNone(alice_entry)
        self.assertFalse(alice_entry["is_archived"])
        self.assertFalse(alice_entry["is_muted"])
        self.assertEqual(alice_entry["last_message"]["content"], "legacy hello")

    def test_opening_legacy_conversation_without_state_still_works(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, content="legacy open")
        self.assertEqual(ConversationState.objects.count(), 0)

        self._auth(self.bob)
        response = self.client.get(f"/api/chat/conversation/{self.alice.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["content"] == "legacy open" for item in response.data))

    def test_legacy_unread_metadata_is_computed_without_state(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, content="legacy unread 1")
        Message.objects.create(sender=self.alice, receiver=self.bob, content="legacy unread 2")
        self.assertEqual(ConversationState.objects.count(), 0)

        self._auth(self.bob)
        users = self._users_payload()
        alice_entry = next((u for u in users if u["id"] == self.alice.id), None)
        self.assertIsNotNone(alice_entry)
        self.assertEqual(alice_entry["unread"], 2)

    def test_opening_conversation_marks_read_and_clears_unread(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, content="first")
        Message.objects.create(sender=self.alice, receiver=self.bob, content="second")

        self._auth(self.bob)
        open_response = self.client.get(f"/api/chat/conversation/{self.alice.id}/")
        self.assertEqual(open_response.status_code, status.HTTP_200_OK)

        users = self._users_payload()
        alice_entry = next((u for u in users if u["id"] == self.alice.id), None)
        self.assertIsNotNone(alice_entry)
        self.assertEqual(alice_entry["unread"], 0)

        state = ConversationState.objects.filter(user=self.bob, other_user=self.alice).first()
        self.assertIsNotNone(state)
        self.assertIsNotNone(state.last_read_at)

    def test_read_state_persists_across_fetches(self):
        msg = Message.objects.create(sender=self.alice, receiver=self.bob, content="persistent read")

        self._auth(self.bob)
        read_response = self.client.post(f"/api/chat/conversation/{self.alice.id}/read/", {}, format="json")
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)

        self._auth(self.alice)
        conversation_response = self.client.get(f"/api/chat/conversation/{self.bob.id}/")
        self.assertEqual(conversation_response.status_code, status.HTTP_200_OK)
        sent_message = next((m for m in conversation_response.data if m["id"] == msg.id), None)
        self.assertIsNotNone(sent_message)
        self.assertTrue(sent_message["read"])

        # Fetch again to ensure state is durable, not transient.
        second_response = self.client.get(f"/api/chat/conversation/{self.bob.id}/")
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        sent_message_again = next((m for m in second_response.data if m["id"] == msg.id), None)
        self.assertIsNotNone(sent_message_again)
        self.assertTrue(sent_message_again["read"])

    def test_mark_read_is_idempotent(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, content="mark me once")

        self._auth(self.bob)
        first = self.client.post(f"/api/chat/conversation/{self.alice.id}/read/", {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        state = ConversationState.objects.get(user=self.bob, other_user=self.alice)
        first_last_read = state.last_read_at

        second = self.client.post(f"/api/chat/conversation/{self.alice.id}/read/", {}, format="json")
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        state.refresh_from_db()

        self.assertEqual(state.last_read_at, first_last_read)

    def test_blocked_users_cannot_send_messages(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        self._auth(self.bob)
        response = self.client.post(
            "/api/chat/send/",
            {"receiver": self.alice.id, "content": "should fail"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("blocked", str(response.data).lower())

    def test_block_rules_prevent_sending_but_do_not_hide_history_visibility(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, content="old history")
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        self._auth(self.bob)
        send_response = self.client.post(
            "/api/chat/send/",
            {"receiver": self.alice.id, "content": "new blocked message"},
            format="json",
        )
        self.assertEqual(send_response.status_code, status.HTTP_403_FORBIDDEN)

        list_users = self._users_payload()
        alice_entry = next((u for u in list_users if u["id"] == self.alice.id), None)
        self.assertIsNotNone(alice_entry)
        self.assertEqual(alice_entry["last_message"]["content"], "old history")

        history_response = self.client.get(f"/api/chat/conversation/{self.alice.id}/")
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["content"] == "old history" for item in history_response.data))

    def test_archive_hides_conversation_from_main_inbox(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, content="archive me")
        self._auth(self.bob)

        archive_response = self.client.post(f"/api/chat/conversation/{self.alice.id}/archive/", {}, format="json")
        self.assertEqual(archive_response.status_code, status.HTTP_200_OK)

        inbox_users = self._users_payload()
        self.assertFalse(any(u["id"] == self.alice.id for u in inbox_users))

        archived_users_response = self.client.get("/api/chat/users/?archived=1")
        self.assertEqual(archived_users_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(u["id"] == self.alice.id for u in archived_users_response.data))

    def test_unarchive_restores_conversation_to_main_inbox(self):
        self._auth(self.bob)
        self.client.post(f"/api/chat/conversation/{self.alice.id}/archive/", {}, format="json")

        unarchive_response = self.client.post(f"/api/chat/conversation/{self.alice.id}/unarchive/", {}, format="json")
        self.assertEqual(unarchive_response.status_code, status.HTTP_200_OK)

        inbox_users = self._users_payload()
        self.assertTrue(any(u["id"] == self.alice.id for u in inbox_users))

    def test_mute_state_persists_on_conversation_list(self):
        self._auth(self.bob)
        mute_response = self.client.post(f"/api/chat/conversation/{self.alice.id}/mute/", {}, format="json")
        self.assertEqual(mute_response.status_code, status.HTTP_200_OK)

        first_users = self._users_payload()
        first_entry = next((u for u in first_users if u["id"] == self.alice.id), None)
        self.assertIsNotNone(first_entry)
        self.assertTrue(first_entry["is_muted"])

        second_users = self._users_payload()
        second_entry = next((u for u in second_users if u["id"] == self.alice.id), None)
        self.assertIsNotNone(second_entry)
        self.assertTrue(second_entry["is_muted"])

    def test_conversation_list_returns_latest_message_and_unread_metadata(self):
        Message.objects.create(sender=self.alice, receiver=self.bob, content="older")
        Message.objects.create(sender=self.alice, receiver=self.bob, content="newer")

        self._auth(self.bob)
        users = self._users_payload()
        alice_entry = next((u for u in users if u["id"] == self.alice.id), None)
        self.assertIsNotNone(alice_entry)
        self.assertEqual(alice_entry["last_message"]["content"], "newer")
        self.assertEqual(alice_entry["unread"], 2)
        self.assertIn("timestamp", alice_entry["last_message"])

    def test_conversation_list_marks_block_flags_and_can_message(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)

        self._auth(self.bob)
        users = self._users_payload()
        alice_entry = next((u for u in users if u["id"] == self.alice.id), None)
        self.assertIsNotNone(alice_entry)
        self.assertTrue(alice_entry["has_blocked_me"])
        self.assertFalse(alice_entry["can_message"])
