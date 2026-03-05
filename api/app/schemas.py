import datetime

from pydantic import BaseModel, Field, field_validator


class SensorReadingCreate(BaseModel):
    sensor_name: str = Field(max_length=100)
    value: float = Field(ge=-1e6, le=1e6)
    # Reject timestamps more than 5 minutes in the future
    recorded_at: datetime.datetime | None = Field(
        default=None,
        description="ISO-8601 timestamp; defaults to server time if omitted.",
    )

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: datetime.datetime | None) -> datetime.datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware.")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if value > now_utc + datetime.timedelta(minutes=5):
            raise ValueError("recorded_at cannot be more than 5 minutes in the future.")
        return value


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
