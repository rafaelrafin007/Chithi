from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save

class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    display_name = models.CharField(max_length=150, blank=True)
    about = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name or self.user.username or str(self.user.id)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile(sender, instance, created, **kwargs):
    # create profile for new users
    if created:
        Profile.objects.create(user=instance)


class FriendRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_DECLINED, "Declined"),
    ]

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="friend_requests_sent",
        on_delete=models.CASCADE,
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="friend_requests_received",
        on_delete=models.CASCADE,
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("from_user", "to_user")

    def __str__(self):
        return f"{self.from_user_id} -> {self.to_user_id} ({self.status})"


def are_friends(user_a, user_b):
    if not user_a or not user_b:
        return False
    return FriendRequest.objects.filter(
        status=FriendRequest.STATUS_ACCEPTED,
        from_user__in=[user_a, user_b],
        to_user__in=[user_a, user_b],
    ).exists()
