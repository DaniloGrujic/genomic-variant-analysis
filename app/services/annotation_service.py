from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotation_file import AnnotationFile

UPLOAD_DIR = Path("uploads/annotation")

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

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    file_path = UPLOAD_DIR / filename

    content = await file.read()
    file_path.write_bytes(content)

    try:
        entry_count = _validate_annotation_file(file_path)

    except (OSError, UnicodeDecodeError, ValueError) as exc:
        file_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid annotation file: {exc}",
        ) from exc

    annotation_file = AnnotationFile(
        project_id=project_id,
        filename=filename,
        file_path=str(file_path),
        file_size=len(content),
        entry_count=entry_count,
    )

    db.add(annotation_file)

    await db.commit()
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

    file_path = Path(annotation_file.file_path)

    if file_path.exists():
        file_path.unlink()

    await db.delete(annotation_file)
    await db.commit()

    return True
