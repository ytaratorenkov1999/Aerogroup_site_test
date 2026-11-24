import math

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def disk_limit() -> float:
    try:
        value = float(getattr(settings, "LIMIT_DISK", 90))
    except (TypeError, ValueError):
        raise ImproperlyConfigured("LIMIT_DISK must be between 0 and 100.") from None
    if not math.isfinite(value) or not 0 < value <= 100:
        raise ImproperlyConfigured("LIMIT_DISK must be between 0 and 100.")
    return value
