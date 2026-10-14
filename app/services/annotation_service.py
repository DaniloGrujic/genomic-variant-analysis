import logging
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation_file import AnnotationFile
from app.models.pending_storage_deletion import PendingStorageDeletion
from app.services.storage_service import (
    StorageError,
    generate_storage_key,
    storage_service,
)

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = [
    "#VariantID",
    "Type",
    "Name",
    "GeneID",
    "GeneSymbol",
    "ClinicalSignificance",
    "RS_dbSNP",
    "Chromosome",
    "Start",
    "Stop",
    "ReferenceAllele",
    "AlternateAllele",
]


def _validate_annotation_file(file_path: Path) -> int:
    valid_entries = 0

    with file_path.open("r", encoding="utf-8") as annotation_file:
        header = annotation_file.readline().strip()

        if not header:
            raise ValueError("Annotation file is empty.")

        columns = header.split("\t")

        if columns != EXPECTED_COLUMNS:
            raise ValueError("Invalid 12-column ClinVar header.")

        for line in annotation_file:
            line = line.strip()

            if not line:
                continue

            fields = line.split("\t")

            if len(fields) != len(EXPECTED_COLUMNS):
                continue

            if not all(field.strip() for field in fields):
                continue

            try:
                int(fields[0])  # VariantID
                int(fields[7].removeprefix("chr"))  # Chromosome
                int(fields[8])  # Start
                int(fields[9])  # Stop
            except ValueError:
                continue

            valid_entries += 1

    return valid_entries


def parse_annotation_entries(file_path: Path) -> list[dict]:
    entries = []

    with file_path.open("r", encoding="utf-8") as annotation_file:
        annotation_file.readline()

        for line in annotation_file:
            line = line.strip()

            if not line:
                continue

            fields = line.split("\t")

            if len(fields) != len(EXPECTED_COLUMNS):
                continue

            if not all(field.strip() for field in fields):
                continue

            chromosome = fields[7]

            if chromosome.lower().startswith("chr"):
                chromosome = chromosome[3:]

            try:
                position = int(fields[8])
            except ValueError:
                continue

            entries.append(
                {
                    "chromosome": chromosome,
                    "position": position,
                    "reference": fields[10],
                    "alternate": fields[11],
                    "gene_name": fields[4],
                    "clinical_significance": fields[5],
                }
            )

    return entries


async def upload_annotation(
    db: AsyncSession,
    project_id: int,
    file: UploadFile,
) -> AnnotationFile:
    filename = file.filename or ""

    if not filename.lower().endswith((".txt", ".tsv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt or .tsv annotation files are allowed.",
        )

    content = await file.read()

    with tempfile.NamedTemporaryFile(
        suffix=".tsv",
        delete=False,
    ) as temp_file:
        temp_file.write(content)
        file_path = Path(temp_file.name)

    try:
        entry_count = _validate_annotation_file(file_path)

    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid annotation file: {exc}",
        ) from exc

    finally:
        file_path.unlink(missing_ok=True)

    key = generate_storage_key(
        "annotation",
        project_id,
        filename,
    )

    storage_reference = await storage_service.save(key, content)

    annotation_file = AnnotationFile(
        project_id=project_id,
        filename=filename,
        file_path=storage_reference,
        file_size=len(content),
        entry_count=entry_count,
    )

    try:
        db.add(annotation_file)
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

    await db.refresh(annotation_file)

    return annotation_file


async def get_annotation_files(
    db: AsyncSession,
    project_id: int,
) -> list[AnnotationFile]:
    result = await db.execute(
        select(AnnotationFile).where(AnnotationFile.project_id == project_id)
    )

    return list(result.scalars().all())


async def delete_annotation_file(
    db: AsyncSession,
    project_id: int,
    annotation_id: int,
) -> bool:
    result = await db.execute(
        select(AnnotationFile).where(
            AnnotationFile.id == annotation_id,
            AnnotationFile.project_id == project_id,
        )
    )

    annotation_file = result.scalar_one_or_none()

    if annotation_file is None:
        return False

    storage_reference = annotation_file.file_path

    # Persist the cleanup job in the same transaction
    # that removes the annotation metadata.
    db.add(
        PendingStorageDeletion(
            storage_reference=storage_reference,
        )
    )

    try:
        await db.delete(annotation_file)
        await db.commit()

    except SQLAlchemyError:
        await db.rollback()
        raise

    return True
