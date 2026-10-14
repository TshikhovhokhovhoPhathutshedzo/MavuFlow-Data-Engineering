from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PipelineStepInput(BaseModel):
    operation: str
    config: dict[str, Any] | None = None


class PipelineCreate(BaseModel):
    name: str
    description: str | None = None
    dataset_id: str
    steps: list[PipelineStepInput]


class PipelineStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pipeline_id: str
    step_order: int
    operation: str
    config: dict[str, Any]


class PipelineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None = None
    user_id: str
    dataset_id: str
    created_at: datetime
    updated_at: datetime
    steps: list[PipelineStepOut]
