from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VariantResponse(BaseModel):
    id: int
    vcf_file_id: int
    chromosome: str
    position: int
    variant_id: str | None
    quality: float | None
    reference: str
    alternate: str
    allele_frequency: float | None

    model_config = ConfigDict(from_attributes=True)


class VCFFileResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    file_path: str
    file_size: int
    variant_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VCFFileDetailResponse(VCFFileResponse):
    variants: list[VariantResponse]
