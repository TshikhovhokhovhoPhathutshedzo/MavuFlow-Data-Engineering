import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_authenticated_user
from app.core.dependencies import get_db
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.pipeline import Pipeline
from app.models.pipeline_step import PipelineStep
from app.models.user import User
from app.schemas.pipeline import PipelineCreate, PipelineOut, PipelineStepOut
from app.services.storage_service import storage_service

router = APIRouter(prefix="/api/v1", tags=["pipelines"])


@router.post("/pipelines", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    payload: PipelineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    dataset = db.query(Dataset).filter(Dataset.id == payload.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")

    pipeline = Pipeline(
        name=payload.name.strip(),
        description=payload.description or "",
        user_id=current_user.id,
        dataset_id=dataset.id,
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    for index, step in enumerate(payload.steps, start=1):
        step_record = PipelineStep(
            pipeline_id=pipeline.id,
            step_order=index,
            operation=step.operation,
            config=json.dumps(step.config or {}),
        )
        db.add(step_record)

    db.commit()
    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "description": pipeline.description,
        "user_id": pipeline.user_id,
        "dataset_id": pipeline.dataset_id,
        "created_at": pipeline.created_at,
        "updated_at": pipeline.updated_at,
        "steps": [
            {
                "id": step.id,
                "pipeline_id": step.pipeline_id,
                "step_order": step.step_order,
                "operation": step.operation,
                "config": json.loads(step.config or "{}"),
            }
            for step in sorted(pipeline.steps, key=lambda item: item.step_order)
        ],
    }


@router.get("/pipelines", response_model=list[PipelineOut])
def list_pipelines(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> list[dict[str, Any]]:
    pipelines = db.query(Pipeline).filter(Pipeline.user_id == current_user.id).order_by(Pipeline.created_at.desc()).all()
    return [
        {
            "id": pipeline.id,
            "name": pipeline.name,
            "description": pipeline.description,
            "user_id": pipeline.user_id,
            "dataset_id": pipeline.dataset_id,
            "created_at": pipeline.created_at,
            "updated_at": pipeline.updated_at,
            "steps": [
                {
                    "id": step.id,
                    "pipeline_id": step.pipeline_id,
                    "step_order": step.step_order,
                    "operation": step.operation,
                    "config": json.loads(step.config or "{}"),
                }
                for step in sorted(pipeline.steps, key=lambda item: item.step_order)
            ],
        }
        for pipeline in pipelines
    ]


@router.get("/pipelines/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    if pipeline.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this pipeline")

    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "description": pipeline.description,
        "user_id": pipeline.user_id,
        "dataset_id": pipeline.dataset_id,
        "created_at": pipeline.created_at,
        "updated_at": pipeline.updated_at,
        "steps": [
            {
                "id": step.id,
                "pipeline_id": step.pipeline_id,
                "step_order": step.step_order,
                "operation": step.operation,
                "config": json.loads(step.config or "{}"),
            }
            for step in sorted(pipeline.steps, key=lambda item: item.step_order)
        ],
    }


@router.post("/pipelines/{pipeline_id}/run")
def run_pipeline(
    pipeline_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, Any]:
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    if pipeline.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this pipeline")

    dataset = db.query(Dataset).filter(Dataset.id == pipeline.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    operations = []
    for step in sorted(pipeline.steps, key=lambda item: item.step_order):
        step_config = json.loads(step.config or "{}")
        operation = {"type": step.operation}
        operation.update(step_config)
        operations.append(operation)

    try:
        result = storage_service.apply_transformations(dataset.storage_key, operations)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    dataset.storage_key = result["output_path"]
    dataset.row_count = result["row_count"]
    dataset.column_count = result["column_count"]
    dataset.status = "transformed"
    dataset.version += 1

    version_record = DatasetVersion(
        dataset_id=dataset.id,
        user_id=current_user.id,
        version_number=dataset.version,
        storage_key=result["output_path"],
        operation="pipeline",
        summary=f"Executed dashboard pipeline: {pipeline.name}",
    )
    db.add(version_record)
    db.commit()
    db.refresh(dataset)

    return {
        "status": "completed",
        "result": result,
    }
