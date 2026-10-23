import gzip
import logging
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.pending_storage_deletion import PendingStorageDeletion
from app.models.variant import Variant
from app.models.vcf_file import VCFFile
from app.services.storage_service import (
    StorageError,
    generate_storage_key,
    storage_service,
)

logger = logging.getLogger(__name__)


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

    content = await file.read()

    with tempfile.NamedTemporaryFile(
        suffix=".vcf.gz" if filename.lower().endswith(".gz") else ".vcf",
        delete=False,
    ) as temp_file:
        temp_file.write(content)
        file_path = Path(temp_file.name)

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
                quality = None if fields[5] == "." else float(fields[5])
                info = fields[7]

                allele_frequency = _parse_af(info)

                variants.append(
                    Variant(
                        chromosome=chromosome,
                        position=position,
                        variant_id=variant_id,
                        quality=quality,
                        reference=reference,
                        alternate=alternate,
                        allele_frequency=allele_frequency,
                    )
                )

    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid VCF file: {exc}",
        ) from exc

    finally:
        file_path.unlink(missing_ok=True)

    key = generate_storage_key("vcf", project_id, filename)
    storage_reference = await storage_service.save(key, content)

    vcf_file = VCFFile(
        project_id=project_id,
        filename=filename,
        file_path=storage_reference,
        file_size=len(content),
        variant_count=len(variants),
    )

    try:
        db.add(vcf_file)
        await db.flush()

        for variant in variants:
            variant.vcf_file_id = vcf_file.id
            db.add(variant)

        await db.commit()

    except SQLAlchemyError:
        await db.rollback()

        try:
            await storage_service.delete(storage_reference)
        except StorageError:
            logger.exception(
                "Failed to clean up uploaded file after database error: %s",
                storage_reference,
            )

        raise

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

    storage_reference = vcf_file.file_path

    # Queue storage deletion and remove VCF metadata atomically.
    db.add(
        PendingStorageDeletion(
            storage_reference=storage_reference,
        )
    )

    try:
        await db.delete(vcf_file)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise

    return True
