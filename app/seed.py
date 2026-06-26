"""
Database seed script.

Generates 200,000 sample products using a single SQL statement.

Why not a Python loop?
----------------------
A naive approach would look like:

    for i in range(200_000):
        db.add(Product(...))
    db.commit()

This is slow for two reasons:
1. Python generates each row one at a time.
2. SQLAlchemy sends 200,000 individual INSERT statements
   (or at best a large VALUES list that takes seconds to build).

What we do instead:

    INSERT INTO products (name, category, price, created_at, updated_at)
    SELECT
        'Product ' || i,
        categories[(i % 10) + 1],
        ...
    FROM generate_series(1, 200000) AS i

generate_series() runs entirely inside PostgreSQL. No data
crosses the network. The database fills itself in one pass.
This is roughly 10-50x faster than a Python loop.

Run:

    python -m app.seed
"""

import time

from sqlalchemy import text

from app.database import Base
from app.database import SessionLocal
from app.database import engine


# ==========================================================
# Configuration
# ==========================================================

TOTAL_PRODUCTS = 200_000

CATEGORIES = [
    "Electronics",
    "Books",
    "Clothing",
    "Sports",
    "Home",
    "Beauty",
    "Furniture",
    "Toys",
    "Automotive",
    "Grocery",
]


# ==========================================================
# Seed Logic
# ==========================================================


def seed_database() -> None:
    """
    Drop existing products and insert 200,000 new ones.

    Uses a single SQL INSERT ... SELECT generate_series(...)
    statement so all work happens inside PostgreSQL.
    """

    print("\nCreating database tables...")
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    try:

        print("Removing existing products...")
        session.execute(text("DELETE FROM products"))
        session.commit()

        print(f"Seeding {TOTAL_PRODUCTS:,} products (single SQL statement)...\n")

        start_time = time.perf_counter()

        # Build the categories array literal for PostgreSQL.
        # e.g. ARRAY['Electronics','Books', ...]
        # We use ::text[] to make the cast explicit.
        categories_literal = (
            "ARRAY["
            + ",".join(f"'{c}'" for c in CATEGORIES)
            + "]::text[]"
        )

        # Single INSERT ... SELECT using generate_series.
        #
        # generate_series(1, 200000) produces rows 1..200000.
        # All column values are computed with SQL expressions:
        #
        #   name        — 'Product 1', 'Product 2', …
        #   category    — cycles through CATEGORIES array
        #   price       — random value between 5.00 and 500.00
        #   created_at  — random timestamp within the last year
        #   updated_at  — created_at + random 0-30 days
        #
        # The entire 200k rows are generated and inserted in
        # one network round-trip.
        sql = text(f"""
            INSERT INTO products (name, category, price, created_at, updated_at)
            SELECT
                'Product ' || i                                         AS name,

                ({categories_literal})[(i % {len(CATEGORIES)}) + 1]    AS category,

                ROUND(
                    (5 + random() * 495)::numeric, 2
                )                                                       AS price,

                NOW() - (random() * INTERVAL '365 days')               AS created_at,

                NOW() - (random() * INTERVAL '365 days')
                    + (random() * INTERVAL '30 days')                  AS updated_at

            FROM generate_series(1, {TOTAL_PRODUCTS}) AS i
        """)

        session.execute(sql)
        session.commit()

        elapsed = time.perf_counter() - start_time

        print(f"Inserted {TOTAL_PRODUCTS:,} products successfully.")
        print(f"Execution time: {elapsed:.2f} seconds\n")

    except Exception as exc:
        session.rollback()
        print(f"Seed failed: {exc}")
        raise

    finally:
        session.close()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":
    seed_database()