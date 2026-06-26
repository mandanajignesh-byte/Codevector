"""
Database models.

Each model represents one database table.

Index Design
------------
The two queries this app runs are:

  1. SELECT * FROM products
     ORDER BY created_at DESC, id DESC
     LIMIT n

  2. SELECT * FROM products
     WHERE category = ?
     ORDER BY created_at DESC, id DESC
     LIMIT n

For query 1 we need an index on (created_at DESC, id DESC).
For query 2 we need an index on (category, created_at DESC, id DESC).

PostgreSQL defaults to ASC for indexes.
Explicitly declaring DESC means the planner can do a forward
index scan instead of a backward scan or in-memory sort.

Why created_at and not updated_at?
------------------------------------
created_at never changes after a product is inserted.
updated_at changes every time a product is modified.

If we sorted by updated_at, a product that gets updated while
a user is browsing would jump to the front of the list.
The user would see it again on the next page — a duplicate.

Sorting by created_at gives a stable, immutable order.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.database import Base


class Product(Base):
    """Product table."""

    __tablename__ = "products"

    __table_args__ = (
        # Used for: browse all products, newest first.
        Index(
            "idx_products_created_id",
            "created_at",
            "id",
            postgresql_ops={
                "created_at": "DESC",
                "id": "DESC",
            },
        ),
        # Used for: browse products filtered by category, newest first.
        Index(
            "idx_products_category_created_id",
            "category",
            "created_at",
            "id",
            postgresql_ops={
                "created_at": "DESC",
                "id": "DESC",
            },
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )