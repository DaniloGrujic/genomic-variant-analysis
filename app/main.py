from fastapi import FastAPI

from app.api.routes.projects import router as projects_router

app = FastAPI(
    title="Variant API",
    description="API for managing genomic variant analysis projects",
    version="0.1.0",
)


app.include_router(projects_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
