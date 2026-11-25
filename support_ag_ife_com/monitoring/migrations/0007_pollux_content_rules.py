from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def seed_pollux_rules(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor,
) -> None:
    alias = schema_editor.connection.alias
    agent = apps.get_model("monitoring", "MonitoringAgent")
    rule = apps.get_model("monitoring", "ContentRule")
    agent_pk = agent.objects.using(alias).filter(
        agent_id="pollux",
    ).values_list("pk", flat=True).first()
    if agent_pk is None:
        return
    defaults = (
        ("DATA_CREWID", "Профили экипажа", 2880),
        ("DATA_CREWLIST", "Экипаж", 180),
        ("DATA_PAXPNL", "Забронированные пассажиры", 120),
        ("DATA_PAXPRL", "Зарегистрированные / допущенные пассажиры", 120),
        ("DATA_XML4OPS", "Планы рейсов", 120),
    )
    for check_id, name, minutes in defaults:
        rule.objects.using(alias).get_or_create(
            agent_id=agent_pk, check_id=check_id, stream_id="DIR",
            defaults={
                "name": name, "silence_limit_minutes": minutes, "enabled": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("monitoring", "0006_content_rules")]
    operations = [
        migrations.RunPython(seed_pollux_rules, migrations.RunPython.noop),
    ]
