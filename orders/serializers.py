from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from .limits import MAX_PRODUCT_ID, MAX_USER_ID
from .models import Order, OrderItem


class OrderLineInputSerializer(serializers.Serializer):
    good_id = serializers.IntegerField(min_value=1, max_value=MAX_PRODUCT_ID)
    quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)


class CreateOrderSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1, max_value=MAX_USER_ID)
    goods = OrderLineInputSerializer(many=True, allow_empty=False)
    promo_code = serializers.CharField(
        required=False, allow_blank=False, max_length=64, trim_whitespace=True
    )

    def validate_goods(self, goods: list[dict[str, int]]) -> list[dict[str, int]]:
        if len(goods) > 100:
            raise serializers.ValidationError(
                "В одном заказе допускается до 100 товаров."
            )
        product_ids = [item["good_id"] for item in goods]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Один товар нельзя передавать несколькими строками."
            )
        return goods


class MoneyField(serializers.Field):
    def to_representation(self, value: Decimal) -> int | float:
        value = Decimal(value).quantize(Decimal("0.01"))
        if value == value.to_integral_value():
            return int(value)
        return float(value)


class DiscountRateField(serializers.Field):
    def to_representation(self, value: Decimal) -> str:
        normalized = format(Decimal(value).normalize(), "f")
        return normalized if normalized != "-0" else "0"


class OrderItemSerializer(serializers.ModelSerializer):
    good_id = serializers.IntegerField(source="product_id")
    price = MoneyField(source="unit_price")
    discount = DiscountRateField(source="discount_rate")
    total = MoneyField()

    class Meta:
        model = OrderItem
        fields = ("good_id", "quantity", "price", "discount", "total")


class OrderSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField()
    order_id = serializers.IntegerField(source="id")
    goods = OrderItemSerializer(source="items", many=True)
    price = MoneyField(source="subtotal")
    discount = DiscountRateField(source="discount_rate")
    total = MoneyField()

    class Meta:
        model = Order
        fields = ("user_id", "order_id", "goods", "price", "discount", "total")
