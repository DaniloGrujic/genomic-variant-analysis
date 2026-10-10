from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.annotation import AnnotationFileResponse
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.vcf import VCFFileDetailResponse, VCFFileResponse
from app.services.annotation_service import (
    delete_annotation_file,
    get_annotation_files,
    upload_annotation,
)
from app.services.project_service import (
    create_project,
    delete_project,
    get_projects,
)
from app.services.vcf_service import (
    delete_vcf_file,
    get_vcf_file,
    get_vcf_files,
    upload_vcf,
)

router = APIRouter(
    prefix="/projects",
)

# ============================================================
# PROJECT ENDPOINTS
# ============================================================


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Projects"],
)
async def create_project_endpoint(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    return await create_project(db, project_data)


@router.get(
    "/",
    response_model=list[ProjectResponse],
    tags=["Projects"],
)
async def list_projects_endpoint(
    db: AsyncSession = Depends(get_db),
):
    return await get_projects(db)


@router.delete(
    "/{project_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Projects"],
)
async def delete_project_endpoint(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_project(db, project_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )


# ============================================================
# VCF ENDPOINTS
# ============================================================


@router.post(
    "/{project_id}/vcf/",
    response_model=VCFFileResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["VCF"],
)
async def upload_vcf_endpoint(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    return await upload_vcf(db, project_id, file)


@router.get(
    "/{project_id}/vcf/",
    response_model=list[VCFFileResponse],
    tags=["VCF"],
)
async def get_vcf_files_endpoint(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await get_vcf_files(db, project_id)


@router.get(
    "/{project_id}/vcf/{vcf_id}",
    response_model=VCFFileDetailResponse,
    tags=["VCF"],
)
async def get_vcf_file_endpoint(
    project_id: int,
    vcf_id: int,
    db: AsyncSession = Depends(get_db),
):
    vcf_file = await get_vcf_file(
        db,
        project_id,
        vcf_id,
    )

    if vcf_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VCF file not found",
        )

    return vcf_file


@router.delete(
    "/{project_id}/vcf/{vcf_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["VCF"],
)
async def delete_vcf_file_endpoint(
    project_id: int,
    vcf_id: int,
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_vcf_file(
        db,
        project_id,
        vcf_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VCF file not found",
        )


# ============================================================
# ANNOTATIONS ENDPOINTS
# ============================================================


@router.post(
    "/{project_id}/annotation/",
    response_model=AnnotationFileResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Annotations"],
)
async def upload_annotation_endpoint(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    return await upload_annotation(
        db,
        project_id,
        file,
    )


@router.get(
    "/{project_id}/annotation/",
    response_model=list[AnnotationFileResponse],
    tags=["Annotations"],
)
async def get_annotation_files_endpoint(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await get_annotation_files(
        db,
        project_id,
    )


@router.delete(
    "/{project_id}/annotation/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Annotations"],
)
async def delete_annotation_file_endpoint(
    project_id: int,
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_annotation_file(
        db,
        project_id,
        annotation_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation file not found",
        )
