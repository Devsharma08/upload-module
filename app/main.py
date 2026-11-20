import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from fastapi import FastAPI, HTTPException, Request, status

from app.api.uploads import router as uploads_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        application.state.db_pool = await asyncpg.create_pool(
            database_url,
            min_size=0,
        )
    else:
        application.state.db_pool = None
    try:
        yield
    finally:
        pool = application.state.db_pool
        if pool is not None:
            await pool.close()


app = FastAPI(
    title="EGCA Pipeline — Stage 1",
    version="0.1.0",
    description="Upload intake and preparation control-plane API.",
    lifespan=lifespan,
)

app.include_router(uploads_router)


@app.get("/healthz", tags=["operations"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["operations"])
async def readiness_check(request: Request) -> dict[str, str]:
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )

    try:
        async with pool.acquire() as connection:
            await connection.execute("SELECT 1")
    except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc

    return {"status": "ready"}
