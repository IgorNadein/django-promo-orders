from django.contrib import admin
from django.http import HttpRequest

from .models import Category, Order, OrderItem, Product, PromoCode, PromoCodeRedemption


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "promotions_allowed")
    list_filter = ("category", "promotions_allowed")
    search_fields = ("name",)


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_percent",
        "valid_from",
        "valid_until",
        "max_uses",
        "category",
        "is_active",
    )
    list_filter = ("is_active", "category")
    search_fields = ("code",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product",
        "product_name",
        "unit_price",
        "quantity",
        "discount_rate",
        "subtotal",
        "total",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "subtotal", "discount_rate", "total", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "promo_code__code")
    readonly_fields = (
        "user",
        "promo_code",
        "subtotal",
        "discount_rate",
        "total",
        "created_at",
    )
    inlines = (OrderItemInline,)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


@admin.register(PromoCodeRedemption)
class PromoCodeRedemptionAdmin(admin.ModelAdmin):
    list_display = ("promo_code", "user", "order", "created_at")
    readonly_fields = ("promo_code", "user", "order", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
