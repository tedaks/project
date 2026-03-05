import datetime

from pydantic import BaseModel, Field


class SensorReadingCreate(BaseModel):
    sensor_name: str = Field(max_length=100)
    value: float = Field(ge=-1e6, le=1e6)
    # Reject timestamps more than 5 minutes in the future
    recorded_at: datetime.datetime | None = Field(
        default=None,
        description="ISO-8601 timestamp; defaults to server time if omitted.",
    )


class SensorReadingOut(BaseModel):
    id: int
    sensor_name: str
    value: float
    recorded_at: datetime.datetime

    model_config = {"from_attributes": True}


class StatsOut(BaseModel):
    sensor_name: str
    count: int
    avg: float
    min: float
    max: float
