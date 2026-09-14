# Changelog

## 0.2.0 — 2026-09-14

- Return a stable HTTP 400 error for line/order monetary overflow before persisting an order.
- Reject oversized input IDs and lock overlapping product sets in primary-key order.
- Test last-use promo races and same-user redemption using real PostgreSQL transactions.
- Verify monetary boundary values, per-line rounding and rollback on a late database error.
- Run the complete suite on PostgreSQL 17 in CI alongside Python 3.10 / 3.12 SQLite checks.
- Align English/Russian documentation with the tested guarantees and input bounds.

## 0.1.0

Initial transactional order API with promo validation, price snapshots and tests.
