from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import CreateOrderSerializer, OrderSerializer
from .services import OrderCreationError, OrderLineInput, create_order


class OrderCreateView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    def post(self, request: Request) -> Response:
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        lines = [
            OrderLineInput(product_id=item["good_id"], quantity=item["quantity"])
            for item in data["goods"]
        ]
        try:
            order = create_order(
                user_id=data["user_id"],
                lines=lines,
                promo_code=data.get("promo_code"),
            )
        except OrderCreationError as exc:
            return Response(
                {exc.field: [{"message": exc.message, "code": exc.code}]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
