# Product Browser — CodeVector Internship Task

A backend that lets someone browse ~200,000 products (newest first), filter by category, and paginate through them — correctly and fast, even while data is changing.

![Product Browser UI](./screenshot.png)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser (Client)                      │
│                                                              │
│   ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│   │ Category     │  │ Load More   │  │ Simulate 50      │  │
│   │ Dropdown     │  │ Button      │  │ Updates Button   │  │
│   └──────┬───────┘  └──────┬──────┘  └────────┬─────────┘  │
│          │                 │                   │            │
│          └─────────────────┴───────────────────┘           │
│                            │                               │
│                  cursor stored in JS memory                │
│                  (not in URL, not in localStorage)         │
└────────────────────────────┬────────────────────────────────┘
                             │  HTTP (fetch)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI  (Python)                         │
│                                                             │
│   GET  /products?cursor=<token>&category=X&limit=20         │
│   GET  /categories                                          │
│   POST /products/simulate-updates                           │
│                                                             │
│   ┌─────────────┐   ┌──────────────┐   ┌───────────────┐  │
│   │  main.py    │──▶│   crud.py    │──▶│ pagination.py │  │
│   │  (routes)   │   │  (queries)   │   │ encode/decode │  │
│   └─────────────┘   └──────┬───────┘   └───────────────┘  │
│                             │                              │
│                    SQLAlchemy ORM                          │
└─────────────────────────────┬───────────────────────────────┘
                              │  psycopg (binary)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  PostgreSQL  (Neon)                          │
│                                                             │
│   Table: products (200,000 rows)                            │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ id │ name │ category │ price │ created_at │ updated_at│ │
│   └──────────────────────────────────────────────────────┘ │
│                                                             │
│   Indexes:                                                  │
│   ┌──────────────────────────────────────────────────────┐ │
│   │ idx_products_created_id                              │ │
│   │   (created_at DESC, id DESC)                         │ │
│   │   → used for: all-products query                     │ │
│   │                                                      │ │
│   │ idx_products_category_created_id                     │ │
│   │   (category, created_at DESC, id DESC)               │ │
│   │   → used for: filtered-by-category query             │ │
│   └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## How Cursor Pagination Works

### The problem with OFFSET

```sql
-- BROKEN approach
SELECT * FROM products ORDER BY created_at DESC OFFSET 200 LIMIT 20
```

If 50 new products are inserted while the user is on page 3, every
subsequent OFFSET shifts by 50. The user skips 50 products or sees
50 duplicates. OFFSET is a row number — it moves when data changes.

### The keyset (cursor) solution

```sql
-- CORRECT approach
SELECT * FROM products
WHERE (created_at < $cursor_created_at)
   OR (created_at = $cursor_created_at AND id < $cursor_id)
ORDER BY created_at DESC, id DESC
LIMIT 20
```

The cursor encodes the `(created_at, id)` of the last product the
client saw. The WHERE clause skips everything before that position.

**Why new inserts don't break it:**
- New products get `created_at = NOW()` — the newest timestamp in the table
- They appear at the front of page 1
- Any existing cursor points to an older `created_at`
- The WHERE clause filters out everything newer than the cursor
- The user's current position is completely unaffected

**Why `created_at` and not `updated_at`:**
- `updated_at` changes every time a product is modified
- A product updated mid-browse would jump to page 1 — duplicate
- `created_at` is immutable after insert — gives a stable, permanent ordering

**Why `id` as tie-breaker:**
- Multiple products can share the same `created_at` (batch inserts)
- `id` is unique, making every cursor position deterministic

---

## Project Structure

```
.
├── app/
│   ├── __init__.py       # Package marker
│   ├── config.py         # Settings via pydantic-settings + .env
│   ├── database.py       # SQLAlchemy engine, session, Base
│   ├── models.py         # Product ORM model + index definitions
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── pagination.py     # Cursor encode / decode (Base64 JSON)
│   ├── crud.py           # All database queries
│   ├── main.py           # FastAPI routes
│   └── seed.py           # Database seed script (generate_series)
├── ui/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── run.py                # Local dev launcher
├── requirements.txt
├── .env.example
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/products` | Paginated product list |
| `GET` | `/products?category=Electronics` | Filtered by category |
| `GET` | `/products?cursor=<token>&limit=20` | Next page |
| `GET` | `/categories` | All unique categories |
| `POST` | `/products/simulate-updates` | Insert 50 new products (demo) |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive API docs (Swagger UI) |

---

## Seed Script

200,000 products are generated using a single SQL statement:

```sql
INSERT INTO products (name, category, price, created_at, updated_at)
SELECT
    'Product ' || i,
    (ARRAY['Electronics','Books',...])[( i % 10) + 1],
    ROUND((5 + random() * 495)::numeric, 2),
    NOW() - (random() * INTERVAL '365 days'),
    NOW() - (random() * INTERVAL '365 days') + (random() * INTERVAL '30 days')
FROM generate_series(1, 200000) AS i
```

`generate_series()` runs entirely inside PostgreSQL — no Python loop,
no data crossing the network. Completes in ~7 seconds vs ~60 seconds
for a Python loop approach.

---

## Local Setup

**1. Clone and install**
```bash
git clone <your-repo-url>
cd Assignment
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
# Edit .env and set your DATABASE_URL
```

```env
DATABASE_URL=postgresql+psycopg://username:password@host/database
```

**3. Seed the database**
```bash
python -m app.seed
```

**4. Run the backend**
```bash
python run.py
# API running at http://127.0.0.1:8000
# Docs at      http://127.0.0.1:8000/docs
```

**5. Run the frontend**
```bash
cd frontend
python -m http.server 3000
# UI at http://127.0.0.1:3000
```

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend | FastAPI | Auto docs, Pydantic validation, fast |
| ORM | SQLAlchemy 2.0 | Type-safe queries, async-ready |
| Driver | psycopg (binary) | Fastest PostgreSQL driver for Python |
| Database | PostgreSQL (Neon) | Native `generate_series`, composite indexes, `timestamptz` |
| Frontend | Vanilla JS | No build step, straightforward, bonus only |

---

## What I'd Improve With More Time

1. **Signed cursors** — replace Base64 JSON with an HMAC token so tampered cursors are rejected cryptographically, not just caught by try/except
2. **Full-text search** — add `name ILIKE` filter with a GIN trigram index
3. **Cache `/categories`** — this scans 200k rows for distinct values; Redis with a short TTL would eliminate that scan
4. **Async SQLAlchemy** — switch to `asyncpg` + async sessions to handle concurrent requests without blocking
5. **Tests** — unit tests for cursor encode/decode, integration test that verifies zero duplicates when products are inserted mid-pagination
