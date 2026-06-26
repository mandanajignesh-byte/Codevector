"""
FastAPI application.
"""

from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.crud import get_categories
from app.crud import get_products
from app.crud import simulate_updates
from app.database import get_db
from app.schemas import CategoriesResponse
from app.schemas import ProductListResponse
from app.schemas import SimulateUpdatesResponse

app = FastAPI(
    title="Product Browser API",
    version="1.0.0",
    description="Backend service for browsing products using cursor pagination.",
)

# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# Root
# ==========================================================

@app.get("/")
def root():
    return {
        "message": "Product Browser API is running."
    }


# ==========================================================
# Health
# ==========================================================

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# ==========================================================
# Categories
# ==========================================================

@app.get(
    "/categories",
    response_model=CategoriesResponse,
)
def categories(
    db: Session = Depends(get_db),
):
    return get_categories(db)


# ==========================================================
# Products
# ==========================================================

@app.get(
    "/products",
    response_model=ProductListResponse,
)
def products(
    category: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        return get_products(
            db=db,
            category=category,
            cursor=cursor,
            limit=limit,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ==========================================================
# Simulate Updates
# ==========================================================

@app.post(
    "/products/simulate-updates",
    response_model=SimulateUpdatesResponse,
)
def products_simulate_updates(
    db: Session = Depends(get_db),
):
    """
    Insert 50 brand-new products with the current timestamp.

    This endpoint exists to demonstrate that cursor pagination
    is stable under live data changes.

    When the client clicks "Simulate Updates":
    - 50 new products appear at the front of the list
      (they have the newest created_at)
    - Any cursor the client is holding still points to the
      same position it did before
    - Continuing to paginate from that cursor will NOT show
      duplicates or skip products

    This proves the correctness guarantee the task asks for.
    """

    try:
        return simulate_updates(db)

    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")