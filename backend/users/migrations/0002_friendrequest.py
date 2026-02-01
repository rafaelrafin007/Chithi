from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FriendRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined")], default="pending", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("from_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="friend_requests_sent", to=settings.AUTH_USER_MODEL)),
                ("to_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="friend_requests_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("from_user", "to_user")},
            },
        ),
    ]
