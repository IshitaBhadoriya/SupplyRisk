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

app = FastAPI(title="SupplyRisk API")
app.include_router(packages.router)


@app.get("/health")
@app.get("/health", tags=["Health"])
def health():
    """Quick check that the API itself is up."""
    return {"status": "ok"}


@app.get("/health/db")
@app.get("/health/db", tags=["Health"])
def health_db(db: Session = Depends(get_db)):
    """Quick check that the API can actually reach Postgres.
    If this returns ok, the whole Docker setup is working end to end."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.get("/packages")
def list_packages(db: Session = Depends(get_db)):
    """Placeholder endpoint — Person A/C will build this out properly.
    Confirms the packages table is queryable."""
    from app.models import Package

    packages = db.query(Package).limit(20).all()
    return [{"id": p.id, "registry": p.registry, "name": p.name} for p in packages]
    return {
        "status": "ok",
        "database": "connected",
    }
