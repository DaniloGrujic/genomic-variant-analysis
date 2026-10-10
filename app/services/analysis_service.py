from pathlib import Path
from statistics import mean, median

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation import Annotation
from app.models.annotation_file import AnnotationFile
from app.models.variant import Variant
from app.models.vcf_file import VCFFile
from app.services.annotation_service import parse_annotation_entries


def _normalize_chromosome(chromosome: str) -> str:
    chromosome = chromosome.strip()

    if chromosome.lower().startswith("chr"):
        chromosome = chromosome[3:]

    return chromosome.lower()


async def annotate_variants(
    db: AsyncSession,
    vcf_id: int,
) -> int:
    result = await db.execute(select(VCFFile).where(VCFFile.id == vcf_id))
    vcf_file = result.scalar_one_or_none()

    if vcf_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VCF file not found.",
        )

    result = await db.execute(
        select(AnnotationFile)
        .where(AnnotationFile.project_id == vcf_file.project_id)
        .order_by(AnnotationFile.created_at.desc(), AnnotationFile.id.desc())
    )
    annotation_file = result.scalars().first()

    if annotation_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation file not found for this project.",
        )

    entries = parse_annotation_entries(Path(annotation_file.file_path))

    annotation_lookup = {
        (
            _normalize_chromosome(entry["chromosome"]),
            entry["position"],
            entry["reference"],
            entry["alternate"],
        ): entry
        for entry in entries
    }

    result = await db.execute(select(Variant).where(Variant.vcf_file_id == vcf_id))
    variants = result.scalars().all()

    variant_ids = [variant.id for variant in variants]

    if variant_ids:
        await db.execute(
            delete(Annotation).where(Annotation.variant_id.in_(variant_ids))
        )

    matched_count = 0

    for variant in variants:
        key = (
            _normalize_chromosome(variant.chromosome),
            variant.position,
            variant.reference,
            variant.alternate,
        )

        entry = annotation_lookup.get(key)

        if entry is None:
            continue

        db.add(
            Annotation(
                variant_id=variant.id,
                gene_name=entry["gene_name"],
                clinical_significance=entry["clinical_significance"],
            )
        )

        matched_count += 1

    await db.commit()

    return matched_count


async def get_filtered_variants(
    db: AsyncSession,
    vcf_id: int,
    min_quality: float | None = None,
    max_quality: float | None = None,
    min_af: float | None = None,
    max_af: float | None = None,
    chrom: str | None = None,
    gene: str | None = None,
    significance: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    result = await db.execute(select(VCFFile.id).where(VCFFile.id == vcf_id))

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VCF file not found.",
        )

    query = (
        select(Variant, Annotation)
        .outerjoin(
            Annotation,
            Annotation.variant_id == Variant.id,
        )
        .where(Variant.vcf_file_id == vcf_id)
        .order_by(Variant.id)
    )

    if min_quality is not None:
        query = query.where(Variant.quality >= min_quality)

    if max_quality is not None:
        query = query.where(Variant.quality <= max_quality)

    if min_af is not None:
        query = query.where(Variant.allele_frequency >= min_af)

    if max_af is not None:
        query = query.where(Variant.allele_frequency <= max_af)

    if chrom is not None:
        normalized_chrom = _normalize_chromosome(chrom)

        query = query.where(
            Variant.chromosome.in_(
                [
                    normalized_chrom,
                    f"chr{normalized_chrom}",
                ]
            )
        )

    if gene is not None:
        query = query.where(Annotation.gene_name == gene)

    if significance is not None:
        query = query.where(Annotation.clinical_significance == significance)

    result = await db.execute(query)
    all_rows = result.all()

    total = len(all_rows)

    rows = all_rows[offset : offset + limit]

    variants = [
        {
            "id": variant.id,
            "chromosome": variant.chromosome,
            "position": variant.position,
            "variant_id": variant.variant_id,
            "reference": variant.reference,
            "alternate": variant.alternate,
            "quality": variant.quality,
            "allele_frequency": variant.allele_frequency,
            "gene": annotation.gene_name if annotation else None,
            "clinical_significance": (
                annotation.clinical_significance if annotation else None
            ),
        }
        for variant, annotation in rows
    ]

    return total, variants


async def get_scientific_summary(
    db: AsyncSession,
    vcf_id: int,
):
    result = await db.execute(select(VCFFile.id).where(VCFFile.id == vcf_id))

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VCF file not found.",
        )

    result = await db.execute(
        select(Variant, Annotation)
        .outerjoin(
            Annotation,
            Annotation.variant_id == Variant.id,
        )
        .where(Variant.vcf_file_id == vcf_id)
    )

    rows = result.all()

    qualities = [variant.quality for variant, _ in rows if variant.quality is not None]

    if qualities:
        quality_statistics = {
            "mean": mean(qualities),
            "median": median(qualities),
            "min": min(qualities),
            "max": max(qualities),
        }
    else:
        quality_statistics = {
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
        }

    af_distribution = {
        "0-0.01": 0,
        "0.01-0.05": 0,
        "0.05-0.1": 0,
        "0.1-0.5": 0,
        "0.5-1.0": 0,
    }

    for variant, _ in rows:
        af = variant.allele_frequency

        if af is None:
            continue

        if af < 0.01:
            af_distribution["0-0.01"] += 1
        elif af < 0.05:
            af_distribution["0.01-0.05"] += 1
        elif af < 0.1:
            af_distribution["0.05-0.1"] += 1
        elif af < 0.5:
            af_distribution["0.1-0.5"] += 1
        else:
            af_distribution["0.5-1.0"] += 1

    gene_counts: dict[str, int] = {}
    significance_counts: dict[str, int] = {}

    for _, annotation in rows:
        if annotation is None:
            continue

        gene_counts[annotation.gene_name] = gene_counts.get(annotation.gene_name, 0) + 1

        significance = annotation.clinical_significance

        significance_counts[significance] = significance_counts.get(significance, 0) + 1

    top_genes = [
        {
            "gene": gene,
            "count": count,
        }
        for gene, count in sorted(
            gene_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:10]
    ]

    return {
        "total_variants": len(rows),
        "quality_statistics": quality_statistics,
        "allele_frequency_distribution": af_distribution,
        "top_genes": top_genes,
        "clinical_significance_counts": significance_counts,
    }


async def get_high_risk_variants(
    db: AsyncSession,
    vcf_id: int,
    min_qual: float = 100,
    min_af: float = 0.1,
):
    result = await db.execute(select(VCFFile.id).where(VCFFile.id == vcf_id))

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VCF file not found.",
        )

    result = await db.execute(
        select(Variant, Annotation)
        .join(
            Annotation,
            Annotation.variant_id == Variant.id,
        )
        .where(
            Variant.vcf_file_id == vcf_id,
            Variant.quality >= min_qual,
            Variant.allele_frequency >= min_af,
            Annotation.clinical_significance.in_(
                [
                    "Pathogenic",
                    "Likely_pathogenic",
                ]
            ),
        )
        .order_by(Variant.id)
    )

    rows = result.all()

    return [
        {
            "id": variant.id,
            "chromosome": variant.chromosome,
            "position": variant.position,
            "variant_id": variant.variant_id,
            "reference": variant.reference,
            "alternate": variant.alternate,
            "quality": variant.quality,
            "allele_frequency": variant.allele_frequency,
            "gene": annotation.gene_name,
            "clinical_significance": annotation.clinical_significance,
        }
        for variant, annotation in rows
    ]
