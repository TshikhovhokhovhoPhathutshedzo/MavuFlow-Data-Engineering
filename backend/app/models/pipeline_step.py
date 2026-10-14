import uuid

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    pipeline_id = Column(String, ForeignKey("pipelines.id"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    operation = Column(String(100), nullable=False)
    config = Column(Text, nullable=False, default="{}")

    pipeline = relationship("Pipeline", back_populates="steps")
