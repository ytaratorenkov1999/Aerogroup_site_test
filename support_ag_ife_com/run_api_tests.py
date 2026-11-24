"""Run only isolated SQLite tests; never import deployed settings."""
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def audit(event: str, args: tuple[Any, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise RuntimeError("Network disabled for offline API tests")
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        name = os.path.basename(os.fsdecode(args[0])).lower()
        if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
            raise RuntimeError("Environment file access disabled")


if __name__ == "__main__":
    sys.addaudithook(audit)
    allowed = {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT"}
    saved = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    os.environ.clear()
    os.environ.update(saved)
    os.environ["DJANGO_SETTINGS_MODULE"] = "test_api_settings"
    os.chdir(ROOT)
    import django
    django.setup()
    from django.core.management import call_command
    call_command("makemigrations", "monitoring", check=True, dry_run=True, verbosity=1)
    from django.test.runner import DiscoverRunner
    failures = DiscoverRunner(verbosity=2, interactive=False).run_tests(["monitoring"])
    raise SystemExit(1 if failures else 0)
