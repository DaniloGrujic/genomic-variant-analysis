from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.project_service import (
    create_project,
    delete_project,
    get_projects,
)

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_endpoint(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    return await create_project(db, project_data)


@router.get(
    "/",
    response_model=list[ProjectResponse],
)
async def list_projects_endpoint(
    db: AsyncSession = Depends(get_db),
):
    return await get_projects(db)


@router.delete(
    "/{project_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
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
