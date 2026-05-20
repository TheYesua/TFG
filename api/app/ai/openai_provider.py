"""Proveedor LLM que usa el cliente oficial de OpenAI.

Características:

* Reintentos exponenciales (``tenacity``) ante errores transitorios:
  ``RateLimitError``, ``APITimeoutError`` y ``APIStatusError`` con código
  5xx. Máximo 4 intentos (≈ 1s, 2s, 4s, 8s).
* Traducción de cualquier error final a :class:`LLMProviderError` para
  aislar a quien llama del cliente concreto.
* Modo ``response_format="json"`` fuerza ``response_format={"type":
  "json_object"}`` en Chat Completions.
"""
from __future__ import annotations

import logging

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .provider import LLMProvider, LLMProviderError, LLMRequest, LLMResponse


logger = logging.getLogger("ai.openai")


# Excepciones de OpenAI que indican fallo transitorio y, por tanto,
# deben provocar un reintento.
def _excepciones_reintentables():
    """Carga perezosamente las clases de excepción de ``openai``."""
    from openai import APITimeoutError, APIConnectionError, RateLimitError, APIStatusError

    return (APITimeoutError, APIConnectionError, RateLimitError, APIStatusError)


class OpenAIProvider:
    """Implementa :class:`LLMProvider` contra la Chat Completions API."""

    nombre = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        modelo: str,
        timeout: int = 120,
        max_intentos: int = 4,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAIProvider requiere api_key no vacía.")
        # Import local para que el paquete ``ai`` pueda importarse aunque
        # ``openai`` no esté disponible en tiempo de test.
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout)
        self._modelo = modelo
        self._max_intentos = max_intentos

    # -- API pública ------------------------------------------------------

    def generar(self, peticion: LLMRequest) -> LLMResponse:
        try:
            return self._invocar_con_reintentos(peticion)
        except Exception as exc:  # incluye LLMProviderError e inesperados
            if isinstance(exc, LLMProviderError):
                raise
            logger.exception("Fallo no recuperable al invocar OpenAI")
            raise LLMProviderError(f"fallo_llm: {exc}") from exc

    # -- internos --------------------------------------------------------

    def _invocar_con_reintentos(self, peticion: LLMRequest) -> LLMResponse:
        reintentables = _excepciones_reintentables()

        @retry(
            reraise=True,
            stop=stop_after_attempt(self._max_intentos),
            wait=wait_exponential(multiplier=1, min=1, max=16),
            retry=retry_if_exception_type(reintentables),
            before_sleep=lambda rs: logger.warning(
                "Reintentando OpenAI (intento %d) tras %s",
                rs.attempt_number,
                rs.outcome.exception().__class__.__name__,
            ),
        )
        def _ejecutar() -> LLMResponse:
            return self._llamar(peticion)

        return _ejecutar()

    def _llamar(self, peticion: LLMRequest) -> LLMResponse:
        mensajes = []
        if peticion.system:
            mensajes.append({"role": "system", "content": peticion.system})
        mensajes.append({"role": "user", "content": peticion.user})

        kwargs: dict = {
            "model": self._modelo,
            "messages": mensajes,
            "temperature": peticion.temperature,
        }
        if peticion.max_tokens is not None:
            # Modelos GPT-5.x usan max_completion_tokens en lugar de max_tokens
            if self._modelo.startswith('gpt-5'):
                kwargs["max_completion_tokens"] = peticion.max_tokens
            else:
                kwargs["max_tokens"] = peticion.max_tokens
        if peticion.response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        respuesta = self._client.chat.completions.create(**kwargs)

        choice = respuesta.choices[0]
        texto = choice.message.content or ""
        usage = getattr(respuesta, "usage", None)

        return LLMResponse(
            texto=texto,
            modelo=respuesta.model,
            tokens_prompt=getattr(usage, "prompt_tokens", None),
            tokens_respuesta=getattr(usage, "completion_tokens", None),
            proveedor=self.nombre,
        )
