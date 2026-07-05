from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.cv import router as cv_router
from app.api.routes.health import router as health_router
from app.api.routes.workspace import router as workspace_router
from app.services.workspace_service import workspace_service


def create_app() -> FastAPI:
    app = FastAPI(title="AI Match Scaffold", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(cv_router)
    app.include_router(workspace_router)

    @app.on_event("startup")
    def startup_event() -> None:
        workspace_service.ensure_runtime_dirs()

    return app


app = create_app()
