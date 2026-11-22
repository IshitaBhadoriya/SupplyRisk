
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import Watchlist, Package, User
from app.schemas.watchlist import WatchlistCreate
from app.services.security import get_current_user

router = APIRouter(
    prefix="/watchlists",
    tags=["Watchlists"],
)


@router.post("/", status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    data: WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    package = db.query(Package).filter(
        Package.id == data.package_id
    ).first()

    if package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    existing = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.package_id == data.package_id,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Package is already in your watchlist",
        )

    entry = Watchlist(
        user_id=current_user.id,
        team_id=None,
        package_id=package.id,
    )

    db.add(entry)

    try:
        db.commit()
        db.refresh(entry)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Package is already in your watchlist",
        )

    return {
        "message": "Package added to watchlist successfully",
        "watchlist": {
            "id": entry.id,
            "user_id": entry.user_id,
            "package_id": package.id,
            "package_name": package.name,
            "registry": package.registry,
            "current_score": package.current_score,
            "added_at": entry.added_at.isoformat(),
        },
    }


@router.get("/")
def get_my_watchlist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entries = (
        db.query(Watchlist, Package)
        .join(Package, Watchlist.package_id == Package.id)
        .filter(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.added_at.desc())
        .all()
    )

    return {
        "user_id": current_user.id,
        "count": len(entries),
        "watchlist": [
            {
                "id": entry.id,
                "package_id": package.id,
                "package_name": package.name,
                "registry": package.registry,
                "repo_url": package.repo_url,
                "current_score": package.current_score,
                "added_at": (
                    entry.added_at.isoformat()
                    if entry.added_at else None
                ),
            }
            for entry, package in entries
        ],
    }


@router.delete("/{package_id}")
def remove_from_watchlist(
    package_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.package_id == package_id,
    ).first()

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found in your watchlist",
        )

    db.delete(entry)
    db.commit()

    return {
        "message": "Package removed from watchlist successfully",
        "package_id": package_id,
    }
