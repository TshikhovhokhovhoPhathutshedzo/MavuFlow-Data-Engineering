from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.auth import get_authenticated_user
from app.core.dependencies import get_db
from app.models.dataset import Dataset
from app.models.dataset_version import DatasetVersion
from app.models.project import Project
from app.models.stored_file import StoredFile
from app.models.user import User
from app.schemas.dataset import (
    DatasetAnalytics,
    DatasetCodeRequest,
    DatasetCleaningRequest,
    DatasetCleaningResult,
    DatasetOut,
    DatasetPreview,
    DatasetProcessRequest,
    DatasetProcessResult,
    DatasetProfile,
    DatasetQualityReport,
    DatasetTransformRequest,
    DatasetTransformResult,
    DatasetVersionOut,
)
from app.services.storage_service import storage_service
from app.services.code_execution_service import code_execution_service

router = APIRouter(prefix="/api/v1", tags=["datasets"])


@router.post("/datasets/upload", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def upload_dataset(
    project_id: str = Form(...),
    name: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> Dataset:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this project")

    if file.filename is None or not file.filename.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A filename is required")
    if Path(file.filename).suffix.lower() not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV and Excel (.xlsx) files are supported")

    dataset = Dataset(
        project_id=project.id,
        user_id=current_user.id,
        name=name or file.filename,
        original_filename=file.filename,
        storage_key="",
        file_extension=Path(file.filename).suffix.lower() or ".dat",
        mime_type=file.content_type or "application/octet-stream",
        file_size=0,
        row_count=0,
        column_count=0,
        version=1,
        status="uploaded",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    try:
        metadata = storage_service.save_upload(current_user.id, project.id, dataset.id, file)
    except ValueError as exc:
        db.delete(dataset)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    dataset.storage_key = metadata["storage_key"]
    dataset.file_size = metadata["file_size"]
    dataset.row_count = metadata["row_count"]
    dataset.column_count = metadata["column_count"]
    dataset.status = "ready"
    dataset.mime_type = metadata["mime_type"]

    stored_file = StoredFile(
        user_id=current_user.id,
        project_id=project.id,
        dataset_id=dataset.id,
        original_filename=file.filename,
        storage_object_key=metadata["storage_key"],
        file_extension=dataset.file_extension,
        mime_type=dataset.mime_type,
        file_size=metadata["file_size"],
        dataset_version=dataset.version,
        processing_status="stored",
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        file_checksum=metadata["checksum"],
        storage_location=metadata["storage_path"],
        created_by=current_user.id,
    )
    db.add(stored_file)

    initial_version = DatasetVersion(
        dataset_id=dataset.id,
        user_id=current_user.id,
        version_number=1,
        storage_key=dataset.storage_key,
        operation="upload",
        summary="Initial dataset upload",
    )
    db.add(initial_version)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> list[Dataset]:
    return (
        db.query(Dataset)
        .filter(Dataset.user_id == current_user.id, Dataset.is_deleted.is_(False))
        .order_by(Dataset.created_at.desc())
        .all()
    )


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    return dataset


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreview)
def get_dataset_preview(
    dataset_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, object]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    if not dataset.storage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file is not available")

    try:
        return storage_service.get_dataset_preview(dataset.storage_key, limit=limit)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/datasets/{dataset_id}/profile", response_model=DatasetProfile)
def get_dataset_profile(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, object]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    if not dataset.storage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file is not available")

    try:
        return storage_service.get_dataset_profile(dataset.storage_key)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/clean", response_model=DatasetCleaningResult)
def clean_dataset(
    dataset_id: str,
    payload: DatasetCleaningRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, object]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    if not dataset.storage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file is not available")
    if not payload.operations:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one cleaning operation is required")

    try:
        cleaned = storage_service.apply_cleaning_operations(dataset.storage_key, [op.model_dump() for op in payload.operations])
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    dataset.storage_key = cleaned["output_path"]
    dataset.row_count = cleaned["row_count"]
    dataset.column_count = cleaned["column_count"]
    dataset.status = "cleaned"
    dataset.version += 1
    db.commit()
    db.refresh(dataset)
    return cleaned


@router.post("/datasets/{dataset_id}/process", response_model=DatasetProcessResult)
def process_dataset(
    dataset_id: str,
    payload: DatasetProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, object]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    if not dataset.storage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file is not available")

    try:
        result = storage_service.process_dataset(
            dataset.storage_key,
            operation=payload.operation,
            mapping=payload.mapping,
            columns=payload.columns,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    dataset.version += 1
    dataset.storage_key = result["output_path"]
    dataset.row_count = result["row_count"]
    dataset.column_count = result["column_count"]
    dataset.status = "processed"

    version_record = DatasetVersion(
        dataset_id=dataset.id,
        user_id=current_user.id,
        version_number=dataset.version,
        storage_key=result["output_path"],
        operation=result["operation"],
        summary=f"Processed using {result['operation']}",
    )
    db.add(version_record)
    db.commit()
    db.refresh(dataset)

    return {
        "status": result["status"],
        "output_path": result["output_path"],
        "row_count": result["row_count"],
        "column_count": result["column_count"],
        "version_number": dataset.version,
        "preview": result["preview"],
        "operation": result["operation"],
    }


@router.post("/datasets/{dataset_id}/transform", response_model=DatasetTransformResult)
def transform_dataset(
    dataset_id: str,
    payload: DatasetTransformRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, object]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    if not dataset.storage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file is not available")
    if not payload.operations:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one transformation is required")

    try:
        result = storage_service.apply_transformations(dataset.storage_key, [op.model_dump() for op in payload.operations])
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    dataset.version += 1
    dataset.storage_key = result["output_path"]
    dataset.row_count = result["row_count"]
    dataset.column_count = result["column_count"]
    dataset.status = "transformed"

    version_record = DatasetVersion(
        dataset_id=dataset.id,
        user_id=current_user.id,
        version_number=dataset.version,
        storage_key=result["output_path"],
        operation="transform",
        summary="Applied dataset transformation operations",
    )
    db.add(version_record)
    db.commit()
    db.refresh(dataset)

    return {
        "status": result["status"],
        "output_path": result["output_path"],
        "row_count": result["row_count"],
        "column_count": result["column_count"],
        "preview": result["preview"],
        "operations": payload.operations,
    }


@router.get("/datasets/{dataset_id}/versions", response_model=list[DatasetVersionOut])
def list_dataset_versions(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> list[DatasetVersion]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    return (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
        .all()
    )


@router.post("/datasets/{dataset_id}/code")
def execute_dataset_code(
    dataset_id: str,
    payload: DatasetCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, object]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    if not dataset.storage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file is not available")

    try:
        result = code_execution_service.execute(dataset.storage_key, payload.code, save=payload.save)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    result["version_number"] = dataset.version
    if payload.save:
        dataset.version += 1
        dataset.storage_key = str(result["output_path"])
        dataset.row_count = int(result["row_count"])
        dataset.column_count = int(result["column_count"])
        dataset.status = "processed"
        result["version_number"] = dataset.version
        db.add(
            DatasetVersion(
                dataset_id=dataset.id,
                user_id=current_user.id,
                version_number=dataset.version,
                storage_key=dataset.storage_key,
                operation="manual_code",
                summary="Applied manual Code Lab changes",
            )
        )
        db.commit()
        db.refresh(dataset)
    return result


@router.get("/datasets/{dataset_id}/analytics", response_model=DatasetAnalytics)
def get_dataset_analytics(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, object]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    if not dataset.storage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file is not available")

    try:
        return storage_service.get_dataset_analytics(dataset.storage_key)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/datasets/{dataset_id}/quality-report", response_model=DatasetQualityReport)
def get_dataset_quality_report(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> dict[str, object]:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    if not dataset.storage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file is not available")

    try:
        return storage_service.get_dataset_quality_report(dataset.storage_key, dataset_id=dataset.id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/datasets/{dataset_id}/export")
def export_dataset(
    dataset_id: str,
    file_format: str = Query("csv", alias="format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
) -> Response:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    if dataset.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this dataset")
    if not dataset.storage_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dataset file is not available")

    try:
        payload, media_type, filename = storage_service.export_dataset(dataset.storage_key, file_format=file_format)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
