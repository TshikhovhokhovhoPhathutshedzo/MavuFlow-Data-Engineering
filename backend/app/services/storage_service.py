import hashlib
import io
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import UploadFile

from app.core.config import settings


class StorageService:
    root_path: Path

    def __init__(self, root_path: str | None = None) -> None:
        self.root_path = Path(root_path or settings.storage_root).resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    def build_user_storage_path(self, user_id: str, project_id: str, dataset_id: str) -> Path:
        return self.root_path / "users" / user_id / "projects" / project_id / "datasets" / dataset_id / "original"

    def save_upload(self, user_id: str, project_id: str, dataset_id: str, file: UploadFile) -> dict[str, Any]:
        allowed = {".csv", ".xlsx"}
        suffix = Path(file.filename or "dataset").suffix.lower()
        if suffix not in allowed:
            raise ValueError("Unsupported file type")

        if file.size and file.size > settings.max_upload_size_mb * 1024 * 1024:
            raise ValueError("File exceeds the configured upload size limit")

        file_bytes = file.file.read()
        if not file_bytes:
            raise ValueError("Uploaded file is empty")

        storage_dir = self.build_user_storage_path(user_id, project_id, dataset_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"original{suffix}"
        target_path = storage_dir / safe_name
        target_path.write_bytes(file_bytes)

        checksum = hashlib.sha256(file_bytes).hexdigest()
        metadata = self._read_dataset_metadata(file_bytes, suffix)

        metadata.update(
            {
                "storage_path": str(target_path),
                "storage_key": str(target_path.relative_to(self.root_path).as_posix()),
                "file_size": len(file_bytes),
                "checksum": checksum,
            }
        )
        return metadata

    def read_dataframe_from_storage(self, storage_key: str) -> pd.DataFrame:
        resolved_path = (self.root_path / storage_key).resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {storage_key}")

        suffix = resolved_path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(resolved_path)
        if suffix == ".json":
            return pd.read_json(resolved_path)
        if suffix == ".xlsx":
            return pd.read_excel(resolved_path)
        raise ValueError(f"Unsupported dataset file type: {suffix}")

    def get_dataset_preview(self, storage_key: str, limit: int = 20) -> dict[str, Any]:
        df = self.read_dataframe_from_storage(storage_key)
        rows = df.head(max(1, min(limit, len(df)))).to_dict(orient="records") if not df.empty else []
        return {
            "columns": list(df.columns),
            "rows": rows,
            "total_rows": int(len(df)),
            "limit": int(limit),
        }

    def get_dataset_profile(self, storage_key: str) -> dict[str, Any]:
        df = self.read_dataframe_from_storage(storage_key)
        columns: list[dict[str, Any]] = []

        for column_name in df.columns:
            series = df[column_name]
            column_profile: dict[str, Any] = {
                "name": str(column_name),
                "dtype": str(series.dtype),
                "null_count": int(series.isnull().sum()),
                "non_null_count": int(series.notna().sum()),
                "unique_count": int(series.nunique(dropna=True)),
            }

            if pd.api.types.is_numeric_dtype(series):
                numeric_values = series.dropna()
                if not numeric_values.empty:
                    column_profile["min"] = float(numeric_values.min())
                    column_profile["max"] = float(numeric_values.max())
                    column_profile["mean"] = float(numeric_values.mean())
            else:
                top_values = series.dropna().value_counts().head(5).to_dict()
                column_profile["top_values"] = {str(key): int(value) for key, value in top_values.items()}

            columns.append(column_profile)

        return {
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "missing_values_total": int(df.isna().sum().sum()),
            "duplicate_rows": int(df.duplicated().sum()),
            "columns": columns,
        }

    def apply_cleaning_operations(self, storage_key: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
        df = self.read_dataframe_from_storage(storage_key)
        for operation in operations:
            operation_type = str(operation.get("type", "")).strip().lower()
            column_name = operation.get("column")

            if operation_type in {"trim_whitespace", "lowercase", "uppercase", "fill_missing", "drop_nulls"}:
                if not column_name:
                    raise ValueError(f"Cleaning operation '{operation_type}' requires a column name")
                if column_name not in df.columns:
                    raise ValueError(f"Column '{column_name}' does not exist in the dataset")

            if operation_type == "trim_whitespace":
                df[column_name] = df[column_name].map(lambda value: value.strip() if isinstance(value, str) else value)
            elif operation_type == "lowercase":
                df[column_name] = df[column_name].map(lambda value: value.lower() if isinstance(value, str) else value)
            elif operation_type == "uppercase":
                df[column_name] = df[column_name].map(lambda value: value.upper() if isinstance(value, str) else value)
            elif operation_type == "fill_missing":
                df[column_name] = df[column_name].fillna(operation.get("value"))
            elif operation_type == "drop_nulls":
                df = df.dropna(subset=[column_name])
            else:
                raise ValueError(f"Unsupported cleaning operation: {operation_type}")

        source_path = (self.root_path / storage_key).resolve()
        version_dir = source_path.parent.parent / "versions"
        version_dir.mkdir(parents=True, exist_ok=True)
        output_path = version_dir / f"cleaned_{uuid4().hex}.csv"
        df.to_csv(output_path, index=False)

        relative_path = str(output_path.relative_to(self.root_path).as_posix())
        preview = df.head(10).to_dict(orient="records")

        return {
            "status": "cleaned",
            "output_path": relative_path,
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "preview": preview,
            "operations": operations,
        }

    def process_dataset(self, storage_key: str, operation: str, mapping: dict[str, str] | None = None, columns: list[str] | None = None) -> dict[str, Any]:
        df = self.read_dataframe_from_storage(storage_key)
        operation_name = str(operation).strip().lower()

        if operation_name == "rename_columns":
            if not mapping:
                raise ValueError("A mapping is required for rename_columns operations")
            df = df.rename(columns={str(key): str(value) for key, value in mapping.items()})
        elif operation_name == "drop_columns":
            if not columns:
                raise ValueError("A columns list is required for drop_columns operations")
            valid_columns = [column for column in columns if column in df.columns]
            df = df.drop(columns=valid_columns)
        elif operation_name == "sort_values":
            column = columns[0] if columns else None
            if not column:
                raise ValueError("A column is required for sort_values operations")
            df = df.sort_values(by=column, kind="mergesort")
        else:
            raise ValueError(f"Unsupported processing operation: {operation_name}")

        source_path = (self.root_path / storage_key).resolve()
        version_dir = source_path.parent.parent / "versions"
        version_dir.mkdir(parents=True, exist_ok=True)
        output_path = version_dir / f"processed_{uuid4().hex}.csv"
        df.to_csv(output_path, index=False)

        relative_path = str(output_path.relative_to(self.root_path).as_posix())
        preview = df.head(10).to_dict(orient="records")

        return {
            "status": "processed",
            "output_path": relative_path,
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "preview": preview,
            "operation": operation_name,
        }

    def apply_transformations(self, storage_key: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
        df = self.read_dataframe_from_storage(storage_key)

        for operation in operations:
            operation_type = str(operation.get("type", "")).strip().lower()
            if operation_type == "rename_columns":
                mapping = operation.get("mapping") or {}
                if not mapping:
                    raise ValueError("A mapping is required for rename_columns operations")
                df = df.rename(columns={str(key): str(value) for key, value in mapping.items()})
            elif operation_type == "compute_column":
                column = operation.get("column")
                expression = operation.get("expression")
                if not column or not expression:
                    raise ValueError("A column and expression are required for compute_column operations")
                df[column] = df.eval(expression, engine="python")
            elif operation_type == "add_column":
                column = operation.get("column")
                if not column:
                    raise ValueError("A column name is required for add_column operations")
                value = operation.get("value")
                df[column] = value
            elif operation_type == "drop_columns":
                columns = operation.get("columns") or []
                if not columns:
                    raise ValueError("A columns list is required for drop_columns operations")
                valid_columns = [column for column in columns if column in df.columns]
                df = df.drop(columns=valid_columns)
            else:
                raise ValueError(f"Unsupported transformation operation: {operation_type}")

        source_path = (self.root_path / storage_key).resolve()
        version_dir = source_path.parent.parent / "versions"
        version_dir.mkdir(parents=True, exist_ok=True)
        output_path = version_dir / f"transformed_{uuid4().hex}.csv"
        df.to_csv(output_path, index=False)

        preview = df.head(10).to_dict(orient="records")
        return {
            "status": "transformed",
            "output_path": str(output_path.relative_to(self.root_path).as_posix()),
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "preview": preview,
            "operations": operations,
        }

    def export_dataset(self, storage_key: str, file_format: str = "csv") -> tuple[bytes, str, str]:
        df = self.read_dataframe_from_storage(storage_key)
        export_format = (file_format or "csv").strip().lower().lstrip(".")

        if export_format == "csv":
            payload = df.to_csv(index=False).encode("utf-8")
            media_type = "text/csv; charset=utf-8"
            filename = "dataset.csv"
        elif export_format == "json":
            payload = df.to_json(orient="records", indent=2).encode("utf-8")
            media_type = "application/json"
            filename = "dataset.json"
        elif export_format in {"xlsx", "excel"}:
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            payload = buffer.getvalue()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "dataset.xlsx"
        else:
            raise ValueError("Unsupported export format: expected csv, json, or xlsx")

        return payload, media_type, filename

    def get_dataset_analytics(self, storage_key: str) -> dict[str, Any]:
        profile = self.get_dataset_profile(storage_key)
        row_count = int(profile["row_count"])
        column_count = int(profile["column_count"])
        missing_values_total = int(profile["missing_values_total"])
        duplicate_rows = int(profile["duplicate_rows"])

        completeness_ratio = 1.0 - (missing_values_total / max(row_count * column_count, 1)) if row_count and column_count else 1.0
        duplicate_ratio = duplicate_rows / max(row_count, 1) if row_count else 0.0
        quality_score = max(0, min(100, round(100 * (0.7 * completeness_ratio + 0.3 * (1.0 - duplicate_ratio)))))

        if quality_score >= 90:
            quality_grade = "excellent"
        elif quality_score >= 75:
            quality_grade = "good"
        elif quality_score >= 60:
            quality_grade = "fair"
        else:
            quality_grade = "poor"

        columns: list[dict[str, Any]] = []
        for column in profile["columns"]:
            null_count = int(column.get("null_count", 0))
            missing_ratio = null_count / max(row_count, 1) if row_count else 0.0
            column_quality_score = max(0, min(100, round(100 * (1.0 - missing_ratio))))
            columns.append(
                {
                    "name": column["name"],
                    "dtype": column.get("dtype", "unknown"),
                    "null_count": null_count,
                    "non_null_count": int(column.get("non_null_count", 0)),
                    "missing_ratio": round(missing_ratio, 4),
                    "quality_score": column_quality_score,
                }
            )

        return {
            "row_count": row_count,
            "column_count": column_count,
            "missing_values_total": missing_values_total,
            "duplicate_rows": duplicate_rows,
            "completeness_ratio": round(completeness_ratio, 4),
            "duplicate_ratio": round(duplicate_ratio, 4),
            "quality_score": quality_score,
            "quality_grade": quality_grade,
            "columns": columns,
        }

    def get_dataset_quality_report(self, storage_key: str, dataset_id: str | None = None) -> dict[str, Any]:
        analytics = self.get_dataset_analytics(storage_key)
        quality_score = int(analytics["quality_score"])

        if quality_score >= 90:
            status = "excellent"
            message = "The dataset is highly complete and reliable for downstream workflows."
        elif quality_score >= 75:
            status = "good"
            message = "The dataset is usable with minor cleaning or validation gaps."
        elif quality_score >= 60:
            status = "fair"
            message = "The dataset has meaningful quality issues that should be reviewed before production use."
        else:
            status = "poor"
            message = "The dataset has substantial missing or duplicate data and requires attention."

        report = {
            "dataset_id": dataset_id,
            "row_count": analytics["row_count"],
            "column_count": analytics["column_count"],
            "missing_values_total": analytics["missing_values_total"],
            "duplicate_rows": analytics["duplicate_rows"],
            "completeness_ratio": analytics["completeness_ratio"],
            "duplicate_ratio": analytics["duplicate_ratio"],
            "quality_score": quality_score,
            "quality_grade": analytics["quality_grade"],
            "summary": {
                "status": status,
                "message": message,
                "completeness_ratio": analytics["completeness_ratio"],
                "duplicate_ratio": analytics["duplicate_ratio"],
            },
            "columns": analytics["columns"],
        }
        return report

    def _read_dataset_metadata(self, file_bytes: bytes, suffix: str) -> dict[str, Any]:
        if suffix == ".csv":
            df = pd.read_csv(io.BytesIO(file_bytes), nrows=100)
            return {
                "row_count": max(int(len(df)), 0),
                "column_count": int(len(df.columns)),
                "mime_type": "text/csv",
            }
        if suffix == ".json":
            data = pd.read_json(io.BytesIO(file_bytes))
            return {
                "row_count": int(len(data)),
                "column_count": int(len(data.columns)),
                "mime_type": "application/json",
            }
        if suffix == ".xlsx":
            df = pd.read_excel(io.BytesIO(file_bytes), nrows=100)
            return {
                "row_count": int(len(df)),
                "column_count": int(len(df.columns)),
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }

        raise ValueError("Unsupported file type")


storage_service = StorageService()
