import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, favorites, media, parks, users
from app.config import settings
from app.database import engine
from app.redis import close_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Shuvit API starting up")
    yield
    await engine.dispose()
    await close_redis()
    logger.info("Shuvit API shut down")


app = FastAPI(
    title="Shuvit API",
    description="Skatepark locator API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
media_dir = settings.MEDIA_DIR
if not os.path.isabs(media_dir):
    media_dir = os.path.join(os.path.dirname(__file__), "..", media_dir)
os.makedirs(media_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_dir), name="media")

app.include_router(parks.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(favorites.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
