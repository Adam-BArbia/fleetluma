"""FL-6 / FL-16 shared report models for LAN and hosted API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Metrics(StrictModel):
    cpu_pct: float = Field(ge=0, le=100)
    ram_used_bytes: int = Field(ge=0)
    ram_total_bytes: int = Field(gt=0)
    disk_path: str = Field(min_length=1)
    disk_used_bytes: int = Field(ge=0)
    disk_total_bytes: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_usage(self):
        if self.ram_used_bytes > self.ram_total_bytes or self.disk_used_bytes > self.disk_total_bytes:
            raise ValueError("Used bytes cannot exceed total")
        return self


class Process(StrictModel):
    pid: int = Field(ge=0)
    name: str
    cpu_pct: float = Field(ge=0)
    memory_bytes: int = Field(ge=0)


class Report(StrictModel):
    sampled_at: datetime
    metrics: Metrics
    processes: list[Process] | None = Field(default=None, max_length=10)


