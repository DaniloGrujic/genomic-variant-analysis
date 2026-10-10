from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analysis import (
    AnalysisVariantResponse,
    AnnotationResult,
    ScientificSummaryResponse,
    VariantFilterResponse,
)
from app.services.analysis_service import (
    annotate_variants,
    get_filtered_variants,
    get_high_risk_variants,
    get_scientific_summary,
)

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"],
)


@router.post(
    "/{vcf_id}/annotate",
    response_model=AnnotationResult,
)
async def annotate_vcf_variants(
    vcf_id: int,
    db: AsyncSession = Depends(get_db),
) -> AnnotationResult:
    matched_variants = await annotate_variants(
        db=db,
        vcf_id=vcf_id,
    )

    return AnnotationResult(
        vcf_id=vcf_id,
        matched_variants=matched_variants,
    )


@router.get(
    "/{vcf_id}/variants",
    response_model=VariantFilterResponse,
)
async def filter_variants(
    vcf_id: int,
    min_quality: float | None = None,
    max_quality: float | None = None,
    min_af: float | None = None,
    max_af: float | None = None,
    chrom: str | None = None,
    gene: str | None = None,
    significance: str | None = None,
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> VariantFilterResponse:
    total, variants = await get_filtered_variants(
        db=db,
        vcf_id=vcf_id,
        min_quality=min_quality,
        max_quality=max_quality,
        min_af=min_af,
        max_af=max_af,
        chrom=chrom,
        gene=gene,
        significance=significance,
        limit=limit,
        offset=offset,
    )

    return VariantFilterResponse(
        total=total,
        limit=limit,
        offset=offset,
        variants=variants,
    )


@router.get(
    "/{vcf_id}/summary",
    response_model=ScientificSummaryResponse,
)
async def scientific_summary(
    vcf_id: int,
    db: AsyncSession = Depends(get_db),
) -> ScientificSummaryResponse:
    summary = await get_scientific_summary(
        db=db,
        vcf_id=vcf_id,
    )

    return ScientificSummaryResponse(**summary)


@router.get(
    "/{vcf_id}/high-risk-variants",
    response_model=list[AnalysisVariantResponse],
)
async def high_risk_variants(
    vcf_id: int,
    min_qual: float = 100,
    min_af: float = 0.1,
    db: AsyncSession = Depends(get_db),
) -> list[AnalysisVariantResponse]:
    variants = await get_high_risk_variants(
        db=db,
        vcf_id=vcf_id,
        min_qual=min_qual,
        min_af=min_af,
    )

    return [AnalysisVariantResponse(**variant) for variant in variants]
