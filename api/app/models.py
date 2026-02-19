import datetime

from sqlalchemy import DateTime, Float, Integer, PrimaryKeyConstraint, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        PrimaryKeyConstraint("id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(Integer, autoincrement=True)
    sensor_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
