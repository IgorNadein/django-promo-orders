from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .limits import MAX_MONEY
from .models import Order, OrderItem, Product, PromoCode, PromoCodeRedemption

MONEY_STEP = Decimal("0.01")
ZERO_RATE = Decimal("0")


@dataclass(frozen=True, slots=True)
class OrderLineInput:
    product_id: int
    quantity: int


class OrderCreationError(Exception):
    def __init__(self, field: str, message: str, *, code: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message
        self.code = code


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def _get_locked_promo(code: str) -> PromoCode:
    try:
        return PromoCode.objects.select_for_update().get(code=code)
    except PromoCode.DoesNotExist as exc:
        raise OrderCreationError(
            "promo_code", "Промокод не найден.", code="promo_not_found"
        ) from exc


def _validate_promo(promo: PromoCode, *, user_id: int) -> None:
    now = timezone.now()
    if not promo.is_active:
        raise OrderCreationError(
            "promo_code", "Промокод отключён.", code="promo_inactive"
        )
    if now < promo.valid_from:
        raise OrderCreationError(
            "promo_code", "Промокод ещё не действует.", code="promo_not_started"
        )
    if now >= promo.valid_until:
        raise OrderCreationError(
            "promo_code", "Срок действия промокода истёк.", code="promo_expired"
        )
    if PromoCodeRedemption.objects.filter(promo_code=promo, user_id=user_id).exists():
        raise OrderCreationError(
            "promo_code",
            "Пользователь уже применял этот промокод.",
            code="promo_already_used",
        )
    if promo.redemptions.count() >= promo.max_uses:
        raise OrderCreationError(
            "promo_code",
            "Лимит использований промокода исчерпан.",
            code="promo_usage_limit_reached",
        )


@transaction.atomic
def create_order(
    *, user_id: int, lines: Sequence[OrderLineInput], promo_code: str | None
) -> Order:
    user_model = get_user_model()
    try:
        user = user_model.objects.select_for_update().get(pk=user_id)
    except user_model.DoesNotExist as exc:
        raise OrderCreationError(
            "user_id", "Пользователь не найден.", code="user_not_found"
        ) from exc

    product_ids = [line.product_id for line in lines]
    products = Product.objects.select_for_update().order_by("pk").in_bulk(product_ids)
    missing_ids = sorted(set(product_ids) - products.keys())
    if missing_ids:
        values = ", ".join(str(product_id) for product_id in missing_ids)
        raise OrderCreationError(
            "goods", f"Товары не найдены: {values}.", code="products_not_found"
        )

    promo = _get_locked_promo(promo_code) if promo_code else None
    if promo is not None:
        _validate_promo(promo, user_id=user.pk)

    promo_rate = (
        Decimal(promo.discount_percent) / Decimal("100") if promo else ZERO_RATE
    )
    item_values: list[dict[str, object]] = []
    subtotal = Decimal("0")
    total = Decimal("0")
    discounted_item_found = False

    for line in lines:
        product = products[line.product_id]
        line_subtotal = _money(product.price * line.quantity)
        eligible = bool(
            promo
            and product.promotions_allowed
            and (promo.category_id is None or promo.category_id == product.category_id)
        )
        line_rate = promo_rate if eligible else ZERO_RATE
        line_total = _money(line_subtotal * (Decimal("1") - line_rate))
        discounted_item_found = discounted_item_found or eligible
        subtotal += line_subtotal
        total += line_total
        if subtotal > MAX_MONEY:
            raise OrderCreationError(
                "goods",
                "Сумма заказа превышает допустимый предел.",
                code="order_total_too_large",
            )
        item_values.append(
            {
                "product": product,
                "product_name": product.name,
                "unit_price": product.price,
                "quantity": line.quantity,
                "discount_rate": line_rate,
                "subtotal": line_subtotal,
                "total": line_total,
            }
        )

    if promo is not None and not discounted_item_found:
        raise OrderCreationError(
            "promo_code",
            "Промокод не применим ни к одному товару заказа.",
            code="promo_not_applicable",
        )

    order = Order.objects.create(
        user=user,
        promo_code=promo,
        subtotal=_money(subtotal),
        discount_rate=promo_rate if promo else ZERO_RATE,
        total=_money(total),
    )
    OrderItem.objects.bulk_create(
        [OrderItem(order=order, **values) for values in item_values]
    )
    if promo is not None:
        PromoCodeRedemption.objects.create(promo_code=promo, user=user, order=order)

    return Order.objects.prefetch_related("items").get(pk=order.pk)
