from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Category, Product, PromoCode


class Command(BaseCommand):
    help = "Create deterministic demo data for local API checks."

    def handle(self, *args: Any, **options: Any) -> None:
        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(username="demo")
        electronics, _ = Category.objects.get_or_create(name="Electronics")
        books, _ = Category.objects.get_or_create(name="Books")
        Product.objects.update_or_create(
            id=1,
            defaults={
                "name": "Keyboard",
                "category": electronics,
                "price": "100.00",
                "promotions_allowed": True,
            },
        )
        Product.objects.update_or_create(
            id=2,
            defaults={
                "name": "Book",
                "category": books,
                "price": "50.00",
                "promotions_allowed": True,
            },
        )
        Product.objects.update_or_create(
            id=3,
            defaults={
                "name": "Gift card",
                "category": electronics,
                "price": "500.00",
                "promotions_allowed": False,
            },
        )
        now = timezone.now()
        PromoCode.objects.update_or_create(
            code="SUMMER2025",
            defaults={
                "discount_percent": 10,
                "valid_from": now - timedelta(days=1),
                "valid_until": now + timedelta(days=30),
                "max_uses": 100,
                "category": None,
                "is_active": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"Demo data ready. user_id={user.pk}, product_ids=1,2,3")
        )
