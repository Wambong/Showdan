from decimal import Decimal
from .models import ExchangeRate

def get_rate(from_currency, to_currency):
    if from_currency == to_currency:
        return Decimal("1")

    direct = ExchangeRate.objects.filter(from_currency=from_currency, to_currency=to_currency).first()
    if direct:
        return direct.rate

    inverse = ExchangeRate.objects.filter(from_currency=to_currency, to_currency=from_currency).first()
    if inverse and inverse.rate:
        return Decimal("1") / inverse.rate

    return None  # no rate available
