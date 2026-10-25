from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Standardized operational health and status check payload schema.

    Attributes:
        status (str): Operational state indicator ('healthy', 'degraded', 'down').
        service (str): Service name identifier.
        version (str): Application semantic release version.
        timestamp (datetime): UTC timestamp of generated health response.
        database (str): Database connectivity state.
        echo (Optional[str]): Echoed client diagnostic message if provided.
    """
    status: str = Field(description="Operational health indicator of the service.")
    service: str = Field(default="heatsafe-backend", description="Service identifier.")
    version: str = Field(default="0.1.0", description="Application semantic version.")
    timestamp: datetime = Field(description="UTC timestamp of generated status.")
    database: str = Field(default="connected", description="Persistence engine status.")
    echo: Optional[str] = Field(default=None, description="Optional diagnostic echo string.")

    model_config = {"from_attributes": True}
