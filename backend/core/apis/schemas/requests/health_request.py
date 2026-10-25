from typing import Optional
from pydantic import BaseModel, Field


class HealthPingRequest(BaseModel):
    """
    Inbound request schema for optional diagnostic ping payload.

    Attributes:
        client_tag (Optional[str]): Diagnostic identifier passed by caller.
        echo_message (Optional[str]): Echo test string for transport validation.
    """
    client_tag: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Diagnostic identifier of the calling service or test runner.",
    )
    echo_message: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional echo test string verified on return.",
    )
