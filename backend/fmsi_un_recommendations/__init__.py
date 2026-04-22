from __future__ import annotations

import sys

import uvicorn
from loguru import logger

from .api import create_app

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)


def main() -> None:
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
