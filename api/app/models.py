import datetime

from sqlalchemy import DateTime, Float, Index, Integer, PrimaryKeyConstraint, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        PrimaryKeyConstraint("id", "recorded_at"),
        # Composite index for sensor_name + time-range queries
        Index("ix_sensor_name_recorded_at", "sensor_name", "recorded_at", postgresql_using="btree"),
        # NOTE: individual column indexes removed — the composite index covers sensor_name
        # queries, and TimescaleDB hypertable partitioning handles recorded_at range scans.
    )

    id: Mapped[int] = mapped_column(Integer, autoincrement=True)
    sensor_name: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
