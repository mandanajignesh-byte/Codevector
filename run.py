"""
Application launcher.

This file provides a simple way to start the FastAPI application
during local development.

Run:

    python run.py

For production deployment (e.g. Render), the application can be
started directly using:

    uvicorn app.main:app
"""

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        app="app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )