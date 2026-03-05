import datetime
import random

from sqlalchemy import insert

from .database import async_session
from .models import SensorReading

SENSOR_NAMES = ["temperature", "humidity", "pressure"]


async def seed_data(count: int = 100) -> int:
    """
    Insert random sensor readings spread over the last 24 hours.

    This function APPENDS to existing data — it does NOT truncate first.
    Use DELETE /api/readings to clear the table before seeding if a clean
    slate is desired.
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    ranges = {
        "temperature": (15.0, 35.0),
        "humidity": (30.0, 90.0),
        "pressure": (980.0, 1040.0),
    }

    rows = []
    for _ in range(count):
        sensor = random.choice(SENSOR_NAMES)
        lo, hi = ranges[sensor]
        rows.append(
            {
                "sensor_name": sensor,
                "value": round(random.uniform(lo, hi), 2),
                "recorded_at": now - datetime.timedelta(seconds=random.randint(0, 86400)),
            }
        )

    async with async_session() as session:
        async with session.begin():
            # Bulk insert — single INSERT with multiple rows, inside explicit transaction
            await session.execute(insert(SensorReading), rows)

    return len(rows)
