from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from orders.models import Category, Product, PromoCode


class ModelValidationTests(TestCase):
    def test_product_rejects_negative_price(self) -> None:
        category = Category.objects.create(name="Books")
        product = Product(name="Invalid", category=category, price=Decimal("-0.01"))

        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_promo_rejects_invalid_validity_window(self) -> None:
        now = timezone.now()
        promo = PromoCode(
            code="INVALID",
            discount_percent=10,
            valid_from=now,
            valid_until=now - timedelta(seconds=1),
            max_uses=1,
        )

        with self.assertRaises(ValidationError):
            promo.full_clean()
