from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.projects import router as projects_router
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Variant API",
    description="API for managing genomic variant analysis projects",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(projects_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
