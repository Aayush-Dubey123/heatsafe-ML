from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime
from backend.core.database.base_class import Base


class ServiceStatus(str, Enum):
    """
    Enumeration of operational service health states.
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class HealthCheckRecord(Base):
    """
    Persistence model recording diagnostic heartbeat ping timestamps.

    Attributes:
        id (int): Primary key identifier.
        service_name (str): Label of component tested (e.g. 'api', 'db').
        status (str): Operational status string.
        checked_at (datetime): UTC timestamp of audit execution.
    """
    __tablename__ = "health_check_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    service_name = Column(String(64), nullable=False, default="heatsafe-backend")
    status = Column(String(32), nullable=False, default=ServiceStatus.HEALTHY.value)
    checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
