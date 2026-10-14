from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatasetCreate(BaseModel):
    project_id: str
    name: str | None = None


class DatasetColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int
    non_null_count: int
    unique_count: int
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    top_values: dict[str, int] | None = None


class DatasetPreview(BaseModel):
    columns: list[str]
    rows: list[dict[str, object]]
    total_rows: int
    limit: int


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    missing_values_total: int
    duplicate_rows: int
    columns: list[DatasetColumnProfile]


class DatasetCleaningOperation(BaseModel):
    type: str
    column: str | None = None
    value: str | int | float | None = None


class DatasetCleaningRequest(BaseModel):
    operations: list[DatasetCleaningOperation]


class DatasetCleaningResult(BaseModel):
    status: str
    output_path: str
    row_count: int
    column_count: int
    preview: list[dict[str, object]]
    operations: list[DatasetCleaningOperation]


class DatasetProcessRequest(BaseModel):
    operation: str
    mapping: dict[str, str] | None = None
    columns: list[str] | None = None


class DatasetTransformOperation(BaseModel):
    type: str
    mapping: dict[str, str] | None = None
    column: str | None = None
    expression: str | None = None
    value: str | int | float | None = None
    columns: list[str] | None = None


class DatasetTransformRequest(BaseModel):
    operations: list[DatasetTransformOperation]


class DatasetCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=12000)
    save: bool = False

    @field_validator("code")
    @classmethod
    def code_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter code before running the dataset")
        return value


class DatasetVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    user_id: str
    version_number: int
    storage_key: str
    operation: str
    summary: str | None = None
    created_at: datetime


class DatasetProcessResult(BaseModel):
    status: str
    output_path: str
    row_count: int
    column_count: int
    version_number: int
    preview: list[dict[str, object]]
    operation: str


class DatasetTransformResult(BaseModel):
    status: str
    output_path: str
    row_count: int
    column_count: int
    preview: list[dict[str, object]]
    operations: list[DatasetTransformOperation]


class DatasetColumnQuality(BaseModel):
    name: str
    dtype: str
    null_count: int
    non_null_count: int
    missing_ratio: float
    quality_score: int


class DatasetAnalytics(BaseModel):
    row_count: int
    column_count: int
    missing_values_total: int
    duplicate_rows: int
    completeness_ratio: float
    duplicate_ratio: float
    quality_score: int
    quality_grade: str
    columns: list[DatasetColumnQuality]


class DatasetQualitySummary(BaseModel):
    status: str
    message: str
    completeness_ratio: float
    duplicate_ratio: float


class DatasetQualityReport(BaseModel):
    dataset_id: str
    row_count: int
    column_count: int
    missing_values_total: int
    duplicate_rows: int
    completeness_ratio: float
    duplicate_ratio: float
    quality_score: int
    quality_grade: str
    summary: DatasetQualitySummary
    columns: list[DatasetColumnQuality]


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    user_id: str
    name: str
    original_filename: str
    storage_key: str
    file_extension: str
    mime_type: str
    file_size: int
    row_count: int
    column_count: int
    version: int
    status: str
    created_at: datetime
    updated_at: datetime
