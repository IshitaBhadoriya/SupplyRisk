
from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    package_id: int = Field(gt=0)


class WatchlistResponse(BaseModel):
    id: int
    user_id: int
    package_id: int
    package_name: str
    registry: str
    current_score: float | None
    added_at: str
