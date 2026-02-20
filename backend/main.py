from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    # Works when running from project root: uvicorn backend.main:app --reload
    from backend.core.database import init_db
    from backend.api.routes import router
except ModuleNotFoundError:
    # Works when running from backend folder: uvicorn main:app --reload
    from core.database import init_db
    from api.routes import router


# Main app entrypoint for Phase 1:
# upload PDF -> extract page text -> persist books/pages.
app = FastAPI(
    title="Booktures 2.0 Backend",
    version="0.1.0",
    description="Phase 1 ingestion and page extraction service.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup_event() -> None:
    # Create DB tables on startup so the project works out-of-the-box.
    init_db()
