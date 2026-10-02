from decimal import Decimal, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter
def rub(value):
    """1500 → «1 500 ₽», 1500.5 → «1 500,5 ₽» (неразрывные пробелы)."""
    amount = Decimal(value or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    whole, frac = f'{amount:,.2f}'.replace(',', ' ').split('.')
    frac = frac.rstrip('0')
    return f"{whole},{frac} ₽" if frac else f"{whole} ₽"
