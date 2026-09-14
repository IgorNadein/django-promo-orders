from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from orders.limits import MAX_MONEY
from orders.models import Category, Order, Product

pytestmark = pytest.mark.django_db


@pytest.fixture
def data() -> tuple[int, Product]:
    user = get_user_model().objects.create_user(username="bounds")
    product = Product.objects.create(
        name="Product",
        category=Category.objects.create(name="Bounds"),
        price=Decimal("10000000.00"),
    )
    return user.pk, product


def test_line_overflow_returns_400_and_no_order(data: tuple[int, Product]) -> None:
    user_id, product = data
    response = APIClient().post(
        "/api/orders/",
        {"user_id": user_id, "goods": [{"good_id": product.pk, "quantity": 1000000}]},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["goods"][0]["code"] == "order_total_too_large"
    assert not Order.objects.exists()


def test_sum_of_valid_lines_cannot_overflow(data: tuple[int, Product]) -> None:
    user_id, product = data
    other = Product.objects.create(
        name="Other",
        category=product.category,
        price=product.price,
    )
    response = APIClient().post(
        "/api/orders/",
        {
            "user_id": user_id,
            "goods": [
                {"good_id": item.pk, "quantity": 50000} for item in (product, other)
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert not Order.objects.exists()


def test_maximum_money_value_is_accepted(data: tuple[int, Product]) -> None:
    user_id, product = data
    product.price = MAX_MONEY
    product.save()
    response = APIClient().post(
        "/api/orders/",
        {"user_id": user_id, "goods": [{"good_id": product.pk, "quantity": 1}]},
        format="json",
    )
    assert response.status_code == 201
    assert Order.objects.get().total == MAX_MONEY


@pytest.mark.parametrize("field", ["user_id", "good_id"])
def test_huge_id_is_validated(data: tuple[int, Product], field: str) -> None:
    user_id, product = data
    response = APIClient().post(
        "/api/orders/",
        {
            "user_id": 10**40 if field == "user_id" else user_id,
            "goods": [
                {"good_id": 10**40 if field == "good_id" else product.pk, "quantity": 1}
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert not Order.objects.exists()
