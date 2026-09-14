# Promo Orders API

A production-style Django REST Framework endpoint for creating an order with an
optional percentage promo code.

## Requirements covered

- validates users, products, quantities and duplicate product lines;
- rejects missing, inactive, future or expired promo codes;
- enforces a global redemption limit;
- allows each user to redeem a promo code only once;
- supports promo codes limited to one product category;
- never discounts products marked as excluded from promotions;
- calculates money with `Decimal` and stores immutable price/discount snapshots;
- protects promo redemption with a database transaction, a locked promo row and
  a unique database constraint;
- returns the response shape specified in the assignment.
- runs linting, type checks and tests for Python 3.10 and 3.12 in GitHub Actions.

## Local setup with SQLite

Python 3.10 or newer and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --dev
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver
```

The API is available at `POST http://127.0.0.1:8000/api/orders/`.

```bash
curl -X POST http://127.0.0.1:8000/api/orders/ \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": 1,
    "goods": [{"good_id": 1, "quantity": 2}],
    "promo_code": "SUMMER2025"
  }'
```

Example response:

```json
{
  "user_id": 1,
  "order_id": 1,
  "goods": [
    {
      "good_id": 1,
      "quantity": 2,
      "price": 100,
      "discount": "0.1",
      "total": 180
    }
  ],
  "price": 200,
  "discount": "0.1",
  "total": 180
}
```

Omit `promo_code` to create an order without a discount.

## PostgreSQL with Docker

PostgreSQL is recommended when checking concurrent promo redemptions because
SQLite does not implement row-level `SELECT FOR UPDATE` locking.

```bash
docker compose up --build --wait
docker compose exec web python manage.py seed_demo
```

The container is exposed at `http://127.0.0.1:8015` by default. Set
`APP_PORT=8000` (or another free port) before `docker compose up` to override it.

## Tests and static checks

```bash
uv run pytest
uv run ruff check .
uv run mypy config orders
```

Or run all checks:

```bash
make check
```

## Design notes

### Transactional promo redemption

Order creation runs inside `transaction.atomic()`. If a promo code is supplied,
its row is selected with `select_for_update()` before checking the redemption
count and creating the order. Concurrent requests for the last available use are
therefore serialized on PostgreSQL. The unique `(promo_code, user)` constraint is
the final guard against repeated redemption by the same user.

### Price snapshots

`OrderItem` stores the product name, unit price, discount rate, subtotal and final
total used when the order was created. Later product or promo changes do not
rewrite historical orders.

### Category and excluded products

A category-limited promo discounts matching products only. Products from other
categories remain in the order at full price. `promotions_allowed=False` always
wins. If no order item is eligible, the API rejects the supplied promo instead of
silently accepting an ineffective code.

### API errors

Business validation errors use HTTP 400 and include a stable machine-readable
code, for example:

```json
{
  "promo_code": [
    {"message": "Срок действия промокода истёк.", "code": "promo_expired"}
  ]
}
```

## Assumptions

- authentication is outside the assignment, so `user_id` is accepted explicitly;
- a request may contain at most 100 distinct product lines;
- a promo code must discount at least one item to be accepted;
- order-level `discount` contains the promo rate while every item contains its
  actual applied rate;
- inventory reservation and payment processing are outside this endpoint.
