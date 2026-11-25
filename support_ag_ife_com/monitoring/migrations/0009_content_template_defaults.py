from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def populate_content_templates(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor,
) -> None:
    template = apps.get_model("monitoring", "MailTemplate")
    manager = template.objects.using(schema_editor.connection.alias)
    body = (
        "Сервер: {server_name}\nПлощадка: {site_id}\n"
        "Дата проверки: {checked_at}\n\n{events}"
    )
    defaults = {
        "problem_subject": "AG-Monitoring: данные не поступают",
        "problem_body": body,
        "recovery_subject": "AG-Monitoring: поступление данных восстановлено",
        "recovery_body": body,
        "error_subject": "AG-Monitoring: обнаружены .err файлы",
        "error_body": body,
        "error_recovery_subject": "AG-Monitoring: ошибки контента устранены",
        "error_recovery_body": body,
    }
    current, _ = manager.get_or_create(category="content", defaults=defaults)
    changes = {
        field: value for field, value in defaults.items()
        if not getattr(current, field)
    }
    if current.problem_subject == "AG-Monitoring: проблема с контентом":
        changes["problem_subject"] = defaults["problem_subject"]
    if current.recovery_subject == "AG-Monitoring: контент — восстановление":
        changes["recovery_subject"] = defaults["recovery_subject"]
    if changes:
        manager.filter(pk=current.pk).update(**changes)


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0008_content_error_templates")]
    operations = [
        migrations.RunPython(populate_content_templates, migrations.RunPython.noop),
    ]
