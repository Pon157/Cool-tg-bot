"""
api/main.py — FastAPI сервер: REST API + раздача webapp статики.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import database as db
from config import settings
from api.routes import router as api_router

logger = logging.getLogger(__name__)

# Теперь документация будет по адресу /docs
app = FastAPI(title="Anon Support Bot API", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Убрали prefix="/api", чтобы фронтенд мог достучаться до /auth/login и прочих
app.include_router(api_router)

# Раздача статики остается прежней
app.mount("/webapp", StaticFiles(directory="webapp", html=True), name="webapp")


@app.on_event("startup")
async def startup() -> None:
    await db.init_pool(settings.POSTGRES_DSN)
    logger.info("API DB pool ready.")


@app.on_event("shutdown")
async def shutdown() -> None:
    if db.pool:
        await db.pool.close()
