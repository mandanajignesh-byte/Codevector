"""
CRUD operations for Product resources.

This module contains all database queries related to products.

Keeping database logic separate from API routes (main.py) means:
- Each function can be tested independently
- Routes stay thin and readable
- Query logic is easy to find and change

Pagination Strategy
-------------------
We use KEYSET (cursor) pagination, not OFFSET pagination.

OFFSET example (what we do NOT do):

    SELECT * FROM products ORDER BY created_at DESC OFFSET 200 LIMIT 20

Problem: if 50 new products are inserted while the user is on
page 3, every subsequent OFFSET shifts by 50. The user skips
50 products or sees 50 duplicates.

KEYSET example (what we DO):

    SELECT * FROM products
    WHERE (created_at, id) < (cursor_created_at, cursor_id)
    ORDER BY created_at DESC, id DESC
    LIMIT 20

The cursor is a position, not a row number. New inserts do not
move it. The user always sees exactly where they left off.

Performance
-----------
The WHERE clause uses the same columns as the index
(created_at DESC, id DESC), so PostgreSQL does an index range
scan: O(log N + page_size) instead of O(N) for large offsets.
"""

import random
from datetime import UTC
from datetime import datetime
from typing import Optional

from sqlalchemy import and_
from sqlalchemy import distinct
from sqlalchemy import insert
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Product
from app.pagination import decode_cursor
from app.pagination import encode_cursor
from app.schemas import CategoriesResponse
from app.schemas import ProductListResponse
from app.schemas import ProductResponse
from app.schemas import SimulateUpdatesResponse


# ==========================================================
# Validation Helpers
# ==========================================================


def _validate_limit(limit: int) -> int:
    """
    Clamp the requested page size to a safe range.

    Without this, a client could request limit=9999999
    and load the entire table into memory.

    Args:
        limit: Requested page size.

    Returns:
        Safe page size between 1 and MAX_PAGE_SIZE.
    """

    if limit <= 0:
        return settings.DEFAULT_PAGE_SIZE

    return min(limit, settings.MAX_PAGE_SIZE)


# ==========================================================
# Query Builder
# ==========================================================


def _build_base_query():
    """
    Start with SELECT * FROM products.

    Returns:
        SQLAlchemy Select object (no filters yet).
    """
    return select(Product)


def _apply_category_filter(query, category: Optional[str]):
    """
    Optionally narrow results to a single category.

    If category is None or empty, the full catalogue is returned.
    The index idx_products_category_created_id has category as
    its leading column, so this filter is fast even on 200k rows.

    Args:
        query:    Current SQLAlchemy query.
        category: Category string from the request, or None.

    Returns:
        Updated query.
    """

    if not category:
        return query

    return query.where(Product.category == category)


def _apply_cursor_filter(query, cursor: Optional[str]):
    """
    Skip every product the client has already seen.

    The cursor encodes the (created_at, id) of the LAST product
    on the previous page. We want products that come AFTER that
    position in descending order, which means BEFORE it in value.

    The WHERE condition handles two cases:

    Case 1 - strictly older created_at:

        Product.created_at < cursor_created_at

        Any product created before the cursor timestamp is
        definitely on a later page.

    Case 2 - same created_at, smaller id:

        Product.created_at == cursor_created_at
        AND Product.id < cursor_id

        Multiple products can share the same created_at.
        Within that tie, we break by id DESC, so "after the
        cursor" means id < cursor_id.

    Together:

        (created_at < cursor_created_at)
        OR
        (created_at == cursor_created_at AND id < cursor_id)

    This is the standard composite keyset condition.

    Why are new inserts invisible behind an existing cursor?

        A new product gets created_at = NOW(), which is newer
        than the cursor's created_at. So it fails BOTH conditions
        and is excluded from the query. It naturally appears at
        the front of page 1 - the user sees it only on refresh.

    Args:
        query:  Current SQLAlchemy query.
        cursor: Encoded cursor string, or None for page 1.

    Returns:
        Updated query.
    """

    if cursor is None:
        return query

    created_at, product_id = decode_cursor(cursor)

    return query.where(
        or_(
            Product.created_at < created_at,
            and_(
                Product.created_at == created_at,
                Product.id < product_id,
            ),
        )
    )


def _apply_sorting(query):
    """
    Sort by created_at DESC, then id DESC as a tie-breaker.

    Why created_at and not updated_at?

    updated_at changes every time a product is modified.
    If we sorted by updated_at, a product modified while a user
    is browsing would jump to the front of the list and appear
    as a duplicate on the next page request.

    created_at never changes after insert. It gives a stable,
    immutable ordering that no update can disrupt.

    Why id as tie-breaker?

    Many products can share the same created_at timestamp
    (e.g. batch inserts). Without a tie-breaker, the database
    can return rows in any order within that timestamp, making
    the cursor ambiguous. id is unique, so it makes every
    position in the list deterministic.

    Returns:
        Updated query.
    """

    return query.order_by(
        Product.created_at.desc(),
        Product.id.desc(),
    )


def _apply_limit(query, limit: int):
    """
    Fetch one extra row beyond the requested page size.

    We never run COUNT(*) to check if another page exists -
    that would scan the whole table on every request.

    Instead, we ask for (limit + 1) rows. If the extra row
    comes back, we know there is a next page. We strip it
    from the response before returning to the client.

    Example with limit=20:
        Database returns 21 rows -> has_more = True
        Database returns 20 rows -> has_more = False

    Args:
        query: Current SQLAlchemy query.
        limit: Validated page size.

    Returns:
        Updated query.
    """

    return query.limit(limit + 1)


# ==========================================================
# Query Execution
# ==========================================================


def _fetch_products(db: Session, query) -> list[Product]:
    """
    Execute the query and return ORM objects.

    Args:
        db:    Database session (provided by FastAPI dependency).
        query: Fully built SQLAlchemy query.

    Returns:
        List of Product ORM instances.
    """

    return db.scalars(query).all()


# ==========================================================
# Response Builder
# ==========================================================


def _build_response(
    products: list[Product],
    limit: int,
) -> ProductListResponse:
    """
    Convert ORM objects into the API response shape.

    Steps:

    1. Check if the extra (limit+1) row came back.
       If yes -> has_more = True, strip the extra row.

    2. Build the next_cursor from the last product's
       (created_at, id). The client sends this cursor
       with its next request.

    3. Serialize each Product ORM object into a
       ProductResponse Pydantic model.

    Args:
        products: Raw list from the database (up to limit+1 items).
        limit:    Requested page size (before the +1).

    Returns:
        ProductListResponse ready to send to the client.
    """

    has_more = len(products) > limit

    if has_more:
        products = products[:-1]

    next_cursor = None

    if has_more and products:
        last = products[-1]
        next_cursor = encode_cursor(
            created_at=last.created_at,
            product_id=last.id,
        )

    return ProductListResponse(
        products=[
            ProductResponse.model_validate(p)
            for p in products
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


# ==========================================================
# Public Functions
# ==========================================================


def get_products(
    db: Session,
    category: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = settings.DEFAULT_PAGE_SIZE,
) -> ProductListResponse:
    """
    Retrieve a paginated page of products.

    Page 1 (no cursor):
        GET /products?limit=20

    Page 2 (with cursor from page 1 response):
        GET /products?cursor=<token>&limit=20

    With category filter:
        GET /products?category=Electronics&limit=20

    Args:
        db:       Database session.
        category: Optional category filter.
        cursor:   Cursor token from the previous response.
        limit:    Number of products per page.

    Returns:
        ProductListResponse containing products + next_cursor.
    """

    limit = _validate_limit(limit)

    query = _build_base_query()
    query = _apply_category_filter(query, category)
    query = _apply_cursor_filter(query, cursor)
    query = _apply_sorting(query)
    query = _apply_limit(query, limit)

    products = _fetch_products(db, query)

    return _build_response(products, limit)


def get_categories(db: Session) -> CategoriesResponse:
    """
    Return all unique product categories, sorted alphabetically.

    Used to populate the category dropdown in the UI.

    Args:
        db: Database session.

    Returns:
        CategoriesResponse with a sorted list of category strings.
    """

    query = (
        select(distinct(Product.category))
        .order_by(Product.category)
    )

    categories = db.scalars(query).all()

    return CategoriesResponse(categories=list(categories))


# ==========================================================
# Simulate Updates
# ==========================================================

CATEGORIES = [
    "Electronics", "Books", "Clothing", "Sports", "Home",
    "Beauty", "Furniture", "Toys", "Automotive", "Grocery",
]

SIMULATE_COUNT = 50


def simulate_updates(db: Session) -> SimulateUpdatesResponse:
    """
    Insert 50 new products with the current timestamp.

    Purpose
    -------
    This function demonstrates that cursor pagination is stable
    when new data arrives while a user is mid-browse.

    What happens when these products are inserted:

    - They get created_at = NOW(), the newest timestamp in
      the table.
    - They appear at the very front of the product list
      (page 1, newest first).
    - Any cursor a client is currently holding encodes an
      older (created_at, id) pair.
    - The keyset WHERE clause filters out everything NEWER
      than the cursor position, so these 50 new products are
      invisible to a client that is already past page 1.
    - The client sees no duplicates and skips nothing.

    This is the core guarantee the task asks for:
    "If 50 new products are added/updated while someone is
    browsing, they must not see the same product twice or
    miss one."

    Args:
        db: Database session.

    Returns:
        SimulateUpdatesResponse with insert count and message.
    """

    now = datetime.now(UTC)

    batch = [
        {
            "name": f"New Product {i + 1}",
            "category": random.choice(CATEGORIES),
            "price": round(random.uniform(5.0, 500.0), 2),
            "created_at": now,
            "updated_at": now,
        }
        for i in range(SIMULATE_COUNT)
    ]

    db.execute(insert(Product), batch)
    db.commit()

    return SimulateUpdatesResponse(
        inserted=SIMULATE_COUNT,
        message=(
            f"{SIMULATE_COUNT} new products inserted with created_at = NOW(). "
            "They appear at the front of the list. "
            "Any cursor you are holding still points to the same position - "
            "continue paginating and you will see no duplicates."
        ),
    )