from datetime import datetime, timezone
from pydantic import BaseModel, Field

class TrafficLog(BaseModel):
    timestamp: datetime=Field(default_factory=lambda: datetime.now(timezone.utc))
    method:str
    path:str
    service:str
    status_code:int
    client_ip:str | None=None

