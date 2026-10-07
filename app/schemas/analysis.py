from pydantic import BaseModel


class AnnotationResult(BaseModel):
    vcf_id: int
    matched_variants: int


class AnalysisVariantResponse(BaseModel):
    id: int
    chromosome: str
    position: int
    variant_id: str | None
    reference: str
    alternate: str
    quality: float | None
    allele_frequency: float | None
    gene: str | None
    clinical_significance: str | None


class VariantFilterResponse(BaseModel):
    total: int
    limit: int
    offset: int
    variants: list[AnalysisVariantResponse]


class QualityStatistics(BaseModel):
    mean: float | None
    median: float | None
    min: float | None
    max: float | None


class GeneCount(BaseModel):
    gene: str
    count: int


class ScientificSummaryResponse(BaseModel):
    total_variants: int
    quality_statistics: QualityStatistics
    allele_frequency_distribution: dict[str, int]
    top_genes: list[GeneCount]
    clinical_significance_counts: dict[str, int]
