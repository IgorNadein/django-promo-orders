from decimal import Decimal

# Matches the precision of Order and OrderItem monetary fields.
MAX_MONEY = Decimal("999999999999.99")
MAX_USER_ID = 2**31 - 1  # Django's built-in User uses AutoField.
MAX_PRODUCT_ID = 2**63 - 1  # Product uses BigAutoField.
