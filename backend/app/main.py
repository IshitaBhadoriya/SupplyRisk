
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import packages
from app.routers.scores import router as scores_router
from app.routers.ingestion import router as ingestion_router
from app.routers.auth import router as auth_router
from app.routers.watchlist import router as watchlist_router

app = FastAPI(
    title="SupplyRisk API",
    description="Open-source package supply-chain risk analysis API",
    version="1.0.0",
)

app.include_router(packages.router)
app.include_router(scores_router)
app.include_router(ingestion_router)
app.include_router(auth_router)
app.include_router(watchlist_router)


@app.get("/health", tags=["Health"])
def health():
    """Quick check that the API itself is up."""
    return {"status": "ok"}


@app.get("/health/db", tags=["Health"])
def health_db(db: Session = Depends(get_db)):
    """Check that the API can actually reach PostgreSQL."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.get("/packages")
def list_packages(db: Session = Depends(get_db)):
    """Placeholder endpoint confirming package table availability."""
    from app.models import Package

    packages = db.query(Package).limit(20).all()
    return [
        {"id": p.id, "registry": p.registry, "name": p.name}
        for p in packages
    ]
