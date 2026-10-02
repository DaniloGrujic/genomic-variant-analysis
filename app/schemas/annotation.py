from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AnnotationFileResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    file_path: str
    file_size: int
    entry_count: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
