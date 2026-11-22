
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import packages

app = FastAPI(
    title="SupplyRisk API",
    description="Open-source package supply-chain risk analysis API",
    version="1.0.0",
)

app.include_router(packages.router)


@app.get("/health", tags=["Health"])
def health():
    """Quick check that the API itself is up."""
    return {
        "status": "ok"
    }


@app.get("/health/db", tags=["Health"])
def health_db(db: Session = Depends(get_db)):
    """Quick check that the API can reach PostgreSQL."""
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "connected",
    }
