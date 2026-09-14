from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from orders.models import (
    Category,
    Order,
    Product,
    PromoCode,
    PromoCodeRedemption,
)


class CreateOrderApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="igor")
        self.other_user = user_model.objects.create_user(username="other")
        self.electronics = Category.objects.create(name="Electronics")
        self.books = Category.objects.create(name="Books")
        self.keyboard = Product.objects.create(
            name="Keyboard",
            category=self.electronics,
            price=Decimal("100.00"),
        )
        self.book = Product.objects.create(
            name="Book", category=self.books, price=Decimal("50.00")
        )
        self.gift_card = Product.objects.create(
            name="Gift card",
            category=self.electronics,
            price=Decimal("500.00"),
            promotions_allowed=False,
        )
        self.url = reverse("orders:order-create")

    def promo(self, **overrides: Any) -> PromoCode:
        now = timezone.now()
        values = {
            "code": "SAVE10",
            "discount_percent": 10,
            "valid_from": now - timedelta(hours=1),
            "valid_until": now + timedelta(days=1),
            "max_uses": 10,
            "category": None,
            "is_active": True,
        }
        values.update(overrides)
        return PromoCode.objects.create(**values)

    def payload(
        self, *, user_id: int | None = None, promo_code: str | None = None
    ) -> dict[str, Any]:
        value = {
            "user_id": user_id or self.user.pk,
            "goods": [{"good_id": self.keyboard.pk, "quantity": 2}],
        }
        if promo_code is not None:
            value["promo_code"] = promo_code
        return value

    def test_creates_order_without_promo(self) -> None:
        response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "user_id": self.user.pk,
                "order_id": response.json()["order_id"],
                "goods": [
                    {
                        "good_id": self.keyboard.pk,
                        "quantity": 2,
                        "price": 100,
                        "discount": "0",
                        "total": 200,
                    }
                ],
                "price": 200,
                "discount": "0",
                "total": 200,
            },
        )
        self.assertEqual(Order.objects.count(), 1)

    def test_applies_valid_promo(self) -> None:
        promo = self.promo()

        response = self.client.post(
            self.url, self.payload(promo_code=promo.code), format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["discount"], "0.1")
        self.assertEqual(response.json()["goods"][0]["discount"], "0.1")
        self.assertEqual(response.json()["total"], 180)
        self.assertTrue(
            PromoCodeRedemption.objects.filter(
                promo_code=promo, user=self.user
            ).exists()
        )

    def test_rejects_unknown_promo_and_rolls_back_order(self) -> None:
        response = self.client.post(
            self.url, self.payload(promo_code="UNKNOWN"), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["promo_code"][0]["code"], "promo_not_found")
        self.assertEqual(Order.objects.count(), 0)

    def test_rejects_expired_promo(self) -> None:
        now = timezone.now()
        promo = self.promo(
            valid_from=now - timedelta(days=2),
            valid_until=now - timedelta(days=1),
        )

        response = self.client.post(
            self.url, self.payload(promo_code=promo.code), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["promo_code"][0]["code"], "promo_expired")

    def test_rejects_promo_that_has_not_started(self) -> None:
        now = timezone.now()
        promo = self.promo(
            valid_from=now + timedelta(days=1),
            valid_until=now + timedelta(days=2),
        )

        response = self.client.post(
            self.url, self.payload(promo_code=promo.code), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["promo_code"][0]["code"], "promo_not_started")

    def test_rejects_reuse_by_same_user(self) -> None:
        promo = self.promo(max_uses=2)
        first = self.client.post(
            self.url, self.payload(promo_code=promo.code), format="json"
        )

        second = self.client.post(
            self.url, self.payload(promo_code=promo.code), format="json"
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["promo_code"][0]["code"], "promo_already_used")
        self.assertEqual(PromoCodeRedemption.objects.count(), 1)

    def test_rejects_promo_after_global_limit(self) -> None:
        promo = self.promo(max_uses=1)
        first = self.client.post(
            self.url, self.payload(promo_code=promo.code), format="json"
        )

        second = self.client.post(
            self.url,
            self.payload(user_id=self.other_user.pk, promo_code=promo.code),
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(
            second.json()["promo_code"][0]["code"], "promo_usage_limit_reached"
        )

    def test_category_promo_only_discounts_matching_products(self) -> None:
        promo = self.promo(category=self.electronics)
        payload = self.payload(promo_code=promo.code)
        payload["goods"] = [
            {"good_id": self.keyboard.pk, "quantity": 1},
            {"good_id": self.book.pk, "quantity": 1},
        ]

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["price"], 150)
        self.assertEqual(body["total"], 140)
        self.assertEqual(body["goods"][0]["discount"], "0.1")
        self.assertEqual(body["goods"][1]["discount"], "0")

    def test_excluded_product_never_receives_discount(self) -> None:
        promo = self.promo()
        payload = self.payload(promo_code=promo.code)
        payload["goods"] = [
            {"good_id": self.keyboard.pk, "quantity": 1},
            {"good_id": self.gift_card.pk, "quantity": 1},
        ]

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["price"], 600)
        self.assertEqual(body["total"], 590)
        self.assertEqual(body["goods"][1]["discount"], "0")

    def test_rejects_promo_when_no_item_is_eligible(self) -> None:
        promo = self.promo(category=self.books)

        response = self.client.post(
            self.url, self.payload(promo_code=promo.code), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["promo_code"][0]["code"], "promo_not_applicable"
        )
        self.assertEqual(Order.objects.count(), 0)

    def test_rejects_duplicate_goods(self) -> None:
        payload = self.payload()
        payload["goods"] = [
            {"good_id": self.keyboard.pk, "quantity": 1},
            {"good_id": self.keyboard.pk, "quantity": 2},
        ]

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("goods", response.json())

    def test_rejects_invalid_quantity(self) -> None:
        payload = self.payload()
        payload["goods"][0]["quantity"] = 0

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)

    def test_rejects_missing_product(self) -> None:
        payload = self.payload()
        payload["goods"][0]["good_id"] = 999_999

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["goods"][0]["code"], "products_not_found")

    def test_rejects_missing_user(self) -> None:
        response = self.client.post(
            self.url, self.payload(user_id=999_999), format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_id"][0]["code"], "user_not_found")
