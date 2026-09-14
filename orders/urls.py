from django.urls import path

from .views import OrderCreateView

app_name = "orders"

urlpatterns = [
    path("orders/", OrderCreateView.as_view(), name="order-create"),
]
