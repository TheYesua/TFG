"""Endpoint de healthcheck que verifica BD y Redis."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from .. import extensions
from ..extensions import db

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Devuelve el estado de los servicios externos críticos."""
    status: dict[str, str] = {"app": "ok"}
    http_code = 200

    # Postgres
    try:
        db.session.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        status["database"] = f"error: {exc.__class__.__name__}"
        http_code = 503

    # Redis (sesiones)
    try:
        if extensions.redis_client is None:
            raise RuntimeError("redis client not initialised")
        extensions.redis_client.ping()
        status["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        status["redis"] = f"error: {exc.__class__.__name__}"
        http_code = 503

    status["model"] = current_app.config.get("OPENAI_MODEL", "")
    return jsonify(status), http_code
