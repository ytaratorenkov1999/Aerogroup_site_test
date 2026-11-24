from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    name = "monitoring"

    def ready(self) -> None:
        from .signals import connect_report_cleanup

        connect_report_cleanup()
