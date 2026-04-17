"""
Configuración centralizada de logging.
Provee un logger con formato consistente para todos los módulos.
"""
import logging
import sys
from app.core.config import config


def setup_logging() -> None:
    """Configura el logger raíz con el nivel definido en .env."""
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def get_logger(name: str) -> logging.Logger:
    """Retorna un logger con nombre de módulo para facilitar el filtrado."""
    return logging.getLogger(name)
