from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def seed_templates(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor,
) -> None:
    template = apps.get_model("monitoring", "MailTemplate")
    body = (
        "Сервер: {server_name}\n"
        "Площадка: {site_id}\n"
        "Дата проверки: {checked_at}\n\n{events}"
    )
    subjects = {
        "disk": (
            "AG-Monitoring: состояние дисков",
            "AG-Monitoring: диски — восстановление",
        ),
        "content": (
            "AG-Monitoring: проблема с контентом",
            "AG-Monitoring: контент — восстановление",
        ),
        "network": (
            "AG-Monitoring: сетевая связность нарушена",
            "AG-Monitoring: сетевая связность восстановлена",
        ),
    }
    for category, (problem, recovery) in subjects.items():
        template.objects.using(schema_editor.connection.alias).get_or_create(
            category=category,
            defaults={
                "problem_subject": problem, "problem_body": body,
                "recovery_subject": recovery, "recovery_body": body,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0004_mail_templates")]
    operations = [migrations.RunPython(seed_templates, migrations.RunPython.noop)]
