from django.db import migrations


def dedupe_reactions(apps, schema_editor):
    MessageReaction = apps.get_model("chat", "MessageReaction")
    # Keep the latest reaction per (message, user), delete older ones
    seen = {}
    for r in MessageReaction.objects.all().order_by("created_at", "id"):
        key = (r.message_id, r.user_id)
        if key in seen:
            # Replace previous with current (latest), delete previous
            prev = seen[key]
            prev.delete()
        seen[key] = r


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0004_messagereaction"),
    ]

    operations = [
        migrations.RunPython(dedupe_reactions, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="messagereaction",
            unique_together={("message", "user")},
        ),
    ]
