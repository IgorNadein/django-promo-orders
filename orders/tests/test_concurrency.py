from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.utils import timezone

from orders.models import Category, Order, Product, PromoCode, PromoCodeRedemption
from orders.services import OrderCreationError, OrderLineInput, create_order

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="Real PostgreSQL row locks required"
    ),
]


@pytest.mark.parametrize("same_user", [False, True])
def test_concurrent_redemption_is_serialized(same_user: bool) -> None:
    users = [
        get_user_model().objects.create_user(username=f"user-{i}") for i in range(2)
    ]
    category = Category.objects.create(name="Race")
    products = [
        Product.objects.create(name=f"P{i}", category=category, price=Decimal("10.00"))
        for i in range(2)
    ]
    promo = PromoCode.objects.create(
        code="LAST",
        discount_percent=10,
        max_uses=10 if same_user else 1,
        valid_from=timezone.now() - timedelta(days=1),
        valid_until=timezone.now() + timedelta(days=1),
    )
    barrier = Barrier(2)

    def submit(index: int) -> str:
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            create_order(
                user_id=users[0 if same_user else index].pk,
                lines=[OrderLineInput(products[index].pk, 1)],
                promo_code=promo.code,
            )
            return "created"
        except OrderCreationError as exc:
            return exc.code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit, (0, 1), timeout=20))
    expected = "promo_already_used" if same_user else "promo_usage_limit_reached"
    assert sorted(outcomes) == sorted(["created", expected])
    assert Order.objects.count() == 1
    assert PromoCodeRedemption.objects.count() == 1


def test_overlapping_product_sets_use_consistent_lock_order() -> None:
    users = [
        get_user_model().objects.create_user(username=f"user-{i}") for i in range(2)
    ]
    category = Category.objects.create(name="Locks")
    products = [
        Product.objects.create(name=f"P{i}", category=category, price=Decimal("10.00"))
        for i in range(2)
    ]
    barrier = Barrier(2)

    def submit(index: int) -> int:
        close_old_connections()
        try:
            lines = [
                OrderLineInput(p.pk, 1)
                for p in (products if index == 0 else list(reversed(products)))
            ]
            barrier.wait(timeout=10)
            return create_order(
                user_id=users[index].pk, lines=lines, promo_code=None
            ).pk
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(submit, (0, 1), timeout=20))
    assert len(set(ids)) == 2
    assert list(Order.objects.values_list("total", flat=True)) == [
        Decimal("20.00"),
        Decimal("20.00"),
    ]
