import datetime

from sqlalchemy import DateTime, Float, Index, Integer, PrimaryKeyConstraint, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        PrimaryKeyConstraint("id", "recorded_at"),
        Index("ix_sensor_name_recorded_at", "sensor_name", "recorded_at", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, autoincrement=True)
    sensor_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
