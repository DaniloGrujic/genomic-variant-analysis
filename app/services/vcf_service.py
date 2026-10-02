import gzip
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.variant import Variant
from app.models.vcf_file import VCFFile

UPLOAD_DIR = Path("uploads/vcf")


def _open_vcf_file(file_path: Path):
    if file_path.suffix == ".gz":
        return gzip.open(file_path, "rt", encoding="utf-8")

    return file_path.open("r", encoding="utf-8")


def _parse_af(info: str) -> float | None:
    if info == ".":
        return None

    for field in info.split(";"):
        if field.startswith("AF="):
            value = field.removeprefix("AF=")

            try:
                return float(value.split(",")[0])
            except ValueError:
                return None

    return None


async def upload_vcf(
    db: AsyncSession,
    project_id: int,
    file: UploadFile,
) -> VCFFile:
    filename = file.filename or ""

    if not filename.lower().endswith((".vcf", ".vcf.gz")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .vcf and .vcf.gz files are allowed.",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    file_path = UPLOAD_DIR / filename

    content = await file.read()
    file_path.write_bytes(content)

    variants = []

    try:
        with _open_vcf_file(file_path) as vcf:
            header_found = False

            for line in vcf:
                line = line.strip()

                if not line:
                    continue

                if line.startswith("##"):
                    continue

                if line.startswith("#CHROM"):
                    header_found = True
                    continue

                if not header_found:
                    raise ValueError("Invalid VCF header.")

                fields = line.split("\t")

                if len(fields) < 8:
                    raise ValueError("Invalid VCF record.")

                chromosome = fields[0]
                position = int(fields[1])
                variant_id = None if fields[2] == "." else fields[2]
                reference = fields[3]
                alternate = fields[4]
                info = fields[7]

                allele_frequency = _parse_af(info)

                variants.append(
                    Variant(
                        chromosome=chromosome,
                        position=position,
                        variant_id=variant_id,
                        reference=reference,
                        alternate=alternate,
                        allele_frequency=allele_frequency,
                    )
                )

    except (OSError, UnicodeDecodeError, ValueError) as exc:
        file_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid VCF file: {exc}",
        ) from exc

    vcf_file = VCFFile(
        project_id=project_id,
        filename=filename,
        file_path=str(file_path),
        file_size=len(content),
        variant_count=len(variants),
    )

    db.add(vcf_file)
    await db.flush()

    for variant in variants:
        variant.vcf_file_id = vcf_file.id
        db.add(variant)

    await db.commit()
    await db.refresh(vcf_file)

    return vcf_file


async def get_vcf_files(
    db: AsyncSession,
    project_id: int,
) -> list[VCFFile]:
    result = await db.execute(select(VCFFile).where(VCFFile.project_id == project_id))

    return list(result.scalars().all())


async def get_vcf_file(
    db: AsyncSession,
    project_id: int,
    vcf_id: int,
) -> VCFFile | None:
    result = await db.execute(
        select(VCFFile)
        .options(selectinload(VCFFile.variants))
        .where(
            VCFFile.id == vcf_id,
            VCFFile.project_id == project_id,
        )
    )

    return result.scalar_one_or_none()


async def delete_vcf_file(
    db: AsyncSession,
    project_id: int,
    vcf_id: int,
) -> bool:
    vcf_file = await get_vcf_file(
        db,
        project_id,
        vcf_id,
    )

    if vcf_file is None:
        return False

    file_path = Path(vcf_file.file_path)

    if file_path.exists():
        file_path.unlink()

    await db.delete(vcf_file)
    await db.commit()

    return True
