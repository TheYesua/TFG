"""Factoría de :class:`LLMProvider` según la configuración de Flask.

Selecciona el proveedor a partir de ``current_app.config``:

* ``AI_PROVIDER = "fake"`` (o sin ``OPENAI_API_KEY``) → :class:`FakeProvider`.
* ``AI_PROVIDER = "openai"`` → :class:`OpenAIProvider`.

El proveedor se construye una sola vez por proceso (caché módulo) para
evitar reabrir clientes HTTP en cada tarea Celery.
"""
from __future__ import annotations

import logging

from flask import current_app

from .fake_provider import FakeProvider
from .openai_provider import OpenAIProvider
from .provider import LLMProvider


logger = logging.getLogger("ai.factory")


_cache: dict[str, LLMProvider] = {}


def get_provider() -> LLMProvider:
    """Devuelve (y cachea) el proveedor configurado para la app actual."""
    cfg = current_app.config
    solicitado = (cfg.get("AI_PROVIDER") or "").lower().strip()
    api_key = cfg.get("OPENAI_API_KEY") or ""

    if solicitado == "fake" or (not solicitado and not api_key):
        return _cache.setdefault("fake", FakeProvider())

    # Por defecto: OpenAI si hay API key o si se pide explícitamente.
    if solicitado in ("", "openai"):
        if not api_key:
            logger.warning(
                "AI_PROVIDER=openai pedido pero no hay OPENAI_API_KEY; "
                "usando FakeProvider como respaldo."
            )
            return _cache.setdefault("fake", FakeProvider())
        if "openai" not in _cache:
            _cache["openai"] = OpenAIProvider(
                api_key=api_key,
                modelo=cfg.get("OPENAI_MODEL") or "gpt-4o-mini",
                timeout=int(cfg.get("OPENAI_TIMEOUT") or 120),
            )
        return _cache["openai"]

    raise ValueError(f"AI_PROVIDER no soportado: {solicitado!r}")


def reset_cache() -> None:
    """Vacía el caché (útil en tests al reconfigurar la app)."""
    _cache.clear()
