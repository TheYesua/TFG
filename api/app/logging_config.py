"""Configuración de logging estructurado con structlog.

Usamos structlog porque permite:

1. Salida JSON en producción (parseable por agregadores tipo Loki/ELK).
2. Salida coloreada legible en desarrollo.
3. ``contextvars`` integrados: cualquier ``bind_contextvars(request_id=...)``
   se propaga a TODO log emitido dentro de la misma petición/tarea, sin
   tener que pasar el ID a mano por cada función.

Esta misma configuración la usan:

* el proceso web (vía ``configure_logging`` desde la app-factory),
* el worker de Celery (vía ``configure_logging`` desde ``celery_worker``),
  además de los signals ``task_prerun``/``task_postrun`` que enlazan el
  ``request_id`` recibido en las cabeceras de la tarea.
"""
from __future__ import annotations

import logging
import os
import sys

import structlog


def configure_logging(*, json_logs: bool | None = None, level: str = "INFO") -> None:
    """Configura ``logging`` estándar + ``structlog`` con processors comunes.

    Args:
        json_logs: ``True`` fuerza salida JSON; ``False`` salida legible;
            ``None`` decide según ``FLASK_ENV`` (json en producción).
        level: Nivel de log raíz (``"INFO"`` por defecto).
    """
    if json_logs is None:
        json_logs = os.environ.get("FLASK_ENV", "production") == "production"

    # Procesadores comunes a stdlib y structlog. ``merge_contextvars``
    # es lo que inyecta request_id (y cualquier otra clave bindada) en
    # todos los eventos sin tocar las llamadas a logger.
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # structlog -> stdlib logging (un único handler real al stderr).
    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Reconfigurar el root logger de stdlib para que los logs de Flask,
    # SQLAlchemy, Celery, etc. también pasen por structlog (con los
    # mismos processors), evitando dos formatos distintos en producción.
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )
    )
    root = logging.getLogger()
    # Evita duplicar handlers si se invoca dos veces (factory + worker).
    root.handlers = [handler]
    root.setLevel(level.upper())

    # Silenciar verborrea de librerías muy ruidosas.
    for noisy in ("werkzeug", "sqlalchemy.engine", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Atajo para obtener un logger estructurado."""
    return structlog.get_logger(name)
