from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    promotions_allowed = models.BooleanField(default=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0), name="product_price_non_negative"
            )
        ]

    def __str__(self) -> str:
        return self.name


class PromoCode(models.Model):
    code = models.CharField(max_length=64, unique=True)
    discount_percent = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    max_uses = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="promo_codes",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)
        constraints = [
            models.CheckConstraint(
                condition=Q(discount_percent__gte=1) & Q(discount_percent__lte=100),
                name="promo_discount_between_1_and_100",
            ),
            models.CheckConstraint(
                condition=Q(max_uses__gte=1), name="promo_max_uses_positive"
            ),
            models.CheckConstraint(
                condition=Q(valid_until__gt=F("valid_from")),
                name="promo_valid_window_ordered",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    promo_code = models.ForeignKey(
        PromoCode,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    discount_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0")
    )
    total = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal__gte=0), name="order_subtotal_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0), name="order_total_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(discount_rate__gte=0) & Q(discount_rate__lte=1),
                name="order_discount_rate_between_0_and_1",
            ),
        ]

    def __str__(self) -> str:
        return f"Order #{self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="order_items"
    )
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    discount_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0")
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1), name="order_item_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0), name="order_item_price_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0), name="order_item_subtotal_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0), name="order_item_total_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(discount_rate__gte=0) & Q(discount_rate__lte=1),
                name="order_item_discount_rate_between_0_and_1",
            ),
            models.UniqueConstraint(
                fields=("order", "product"), name="unique_product_per_order"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product_name} × {self.quantity}"


class PromoCodeRedemption(models.Model):
    promo_code = models.ForeignKey(
        PromoCode, on_delete=models.PROTECT, related_name="redemptions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="promo_redemptions",
    )
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="promo_redemption"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("promo_code", "user"),
                name="unique_promo_redemption_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.promo_code.code}: {self.user_id}"
