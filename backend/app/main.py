from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.categories.router import router as categories_router
from app.imports.router import router as imports_router
from app.invitations.router import router as invitations_router
from app.notifications.router import router as notifications_router
from app.projects.router import router as projects_router
from app.reviews.router import router as reviews_router

app = FastAPI(title="ReviewRadar API")
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(categories_router)
app.include_router(reviews_router)
app.include_router(imports_router)
app.include_router(invitations_router)
app.include_router(notifications_router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
