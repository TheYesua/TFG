"""Servicio de aplicación para Situaciones de Aprendizaje.

Aísla la lógica de negocio (autorización, versionado, duplicación) de la capa
HTTP. Los blueprints solo orquestan: validan entrada, llaman al servicio y
serializan la salida.
"""
from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Query

from ..extensions import db
from ..models import SituacionAprendizaje, Usuario, Version


# ---------------------------------------------------------------------------
# Errores propios
# ---------------------------------------------------------------------------


class SituacionError(Exception):
    """Error de dominio para operaciones sobre situaciones de aprendizaje."""

    def __init__(self, code: str, message: str = "", http_status: int = 400) -> None:
        super().__init__(message or code)
        self.code = code
        self.http_status = http_status


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


# Campos que se incluyen en el snapshot de versión (toda la "carga" del SA).
_CAMPOS_VERSIONABLES = (
    "titulo",
    "curso",
    "materia",
    "comunidad_autonoma",
    "descripcion",
    "metodologia",
    "num_sesiones",
    "duracion_sesion_minutos",
    "idioma",
    "perfil_aula",
    "materiales_contexto",
    "contenido",
    "estado",
    "tipo_adaptacion",
    "perfil_alumnado",
)


def _snapshot(sa: SituacionAprendizaje) -> dict[str, Any]:
    """Devuelve un dict serializable con el estado actual del SA."""
    return {campo: copy.deepcopy(getattr(sa, campo)) for campo in _CAMPOS_VERSIONABLES}


def _verificar_propietario(sa: SituacionAprendizaje, usuario: Usuario) -> None:
    """Solo el dueño o un administrador pueden tocar la situación."""
    if usuario.es_administrador:
        return
    if sa.id_usuario != usuario.id_usuario:
        raise SituacionError("permiso_denegado", http_status=403)


def _proximo_numero_version(id_situacion: int) -> int:
    """Calcula el siguiente número de versión secuencial."""
    actual = db.session.scalar(
        select(db.func.max(Version.numero_version)).where(
            Version.id_situacion == id_situacion
        )
    )
    return (actual or 0) + 1


# ---------------------------------------------------------------------------
# Operaciones
# ---------------------------------------------------------------------------


def crear(usuario: Usuario, datos: dict[str, Any]) -> SituacionAprendizaje:
    """Crea una nueva situación de aprendizaje propiedad del usuario dado."""
    sa = SituacionAprendizaje(id_usuario=usuario.id_usuario, **datos)
    db.session.add(sa)
    db.session.commit()
    return sa


def listar(
    usuario: Usuario,
    *,
    curso: str | None = None,
    materia: str | None = None,
    estado: str | None = None,
    q: str | None = None,
    incluir_adaptaciones: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> list[SituacionAprendizaje]:
    """Lista las situaciones del usuario aplicando los filtros indicados.

    Los administradores ven todas; el resto solo las suyas.
    """
    stmt = select(SituacionAprendizaje)

    if not usuario.es_administrador:
        stmt = stmt.where(SituacionAprendizaje.id_usuario == usuario.id_usuario)

    if curso:
        stmt = stmt.where(SituacionAprendizaje.curso == curso)
    if materia:
        stmt = stmt.where(SituacionAprendizaje.materia == materia)
    if estado:
        stmt = stmt.where(SituacionAprendizaje.estado == estado)
    if q:
        stmt = stmt.where(SituacionAprendizaje.titulo.ilike(f"%{q}%"))
    if not incluir_adaptaciones:
        stmt = stmt.where(SituacionAprendizaje.id_situacion_origen.is_(None))

    stmt = (
        stmt.order_by(SituacionAprendizaje.fecha_modificacion.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.session.scalars(stmt).all())


def obtener(id_situacion: int, usuario: Usuario) -> SituacionAprendizaje:
    """Devuelve la situación si el usuario tiene acceso, o lanza error."""
    sa = db.session.get(SituacionAprendizaje, id_situacion)
    if sa is None:
        raise SituacionError("no_encontrada", http_status=404)
    _verificar_propietario(sa, usuario)
    return sa


def actualizar(
    id_situacion: int,
    usuario: Usuario,
    cambios: dict[str, Any],
) -> SituacionAprendizaje:
    """Aplica los cambios y crea una nueva Version con el estado **previo**.

    De este modo, la última versión guardada siempre representa la situación
    inmediatamente antes del último guardado, lo que permite restaurar.
    """
    sa = obtener(id_situacion, usuario)

    descripcion_cambio = cambios.pop("descripcion_cambio", None)

    # Los estados "generando" y "error_generacion" son gestionados por el
    # backend (tarea de generación). El docente puede pasar a "borrador",
    # "generada" o "finalizada" manualmente, pero no reclamar un estado
    # transitorio/error.
    nuevo_estado = cambios.get("estado")
    if nuevo_estado in (SituacionAprendizaje.GENERANDO, SituacionAprendizaje.ERROR_GENERACION):
        raise SituacionError(
            "estado_no_editable_manualmente",
            "El estado 'generando'/'error_generacion' lo gestiona el backend.",
            http_status=409,
        )

    if not cambios:
        return sa  # nada que hacer; no creamos versión vacía

    # 1) Snapshot del estado actual ANTES de aplicar los cambios
    version = Version(
        id_situacion=sa.id_situacion,
        numero_version=_proximo_numero_version(sa.id_situacion),
        contenido=_snapshot(sa),
        descripcion_cambio=descripcion_cambio,
    )
    db.session.add(version)

    # 2) Aplicar cambios sobre la situación
    for campo, valor in cambios.items():
        setattr(sa, campo, valor)

    db.session.commit()
    return sa


def eliminar(id_situacion: int, usuario: Usuario) -> None:
    """Elimina la situación (y sus versiones por cascade)."""
    sa = obtener(id_situacion, usuario)
    db.session.delete(sa)
    db.session.commit()


def duplicar(
    id_situacion: int,
    usuario: Usuario,
    nuevo_titulo: str | None = None,
) -> SituacionAprendizaje:
    """Crea una copia independiente de la situación dada.

    El usuario que duplica pasa a ser el dueño. La copia arranca como
    ``borrador`` y sin historial de versiones (es una nueva situación).
    """
    original = obtener(id_situacion, usuario)

    titulo = nuevo_titulo or f"{original.titulo} (copia)"
    copia = SituacionAprendizaje(
        id_usuario=usuario.id_usuario,
        titulo=titulo,
        curso=original.curso,
        materia=original.materia,
        comunidad_autonoma=original.comunidad_autonoma,
        descripcion=original.descripcion,
        metodologia=original.metodologia,
        num_sesiones=original.num_sesiones,
        duracion_sesion_minutos=original.duracion_sesion_minutos,
        idioma=original.idioma,
        perfil_aula=original.perfil_aula,
        materiales_contexto=original.materiales_contexto,
        contenido=copy.deepcopy(original.contenido),
        estado=SituacionAprendizaje.BORRADOR,
        # No heredamos id_situacion_origen ni tipo_adaptacion: una "copia"
        # no es una "adaptación curricular" (que se modela aparte).
    )
    db.session.add(copia)
    db.session.commit()
    return copia


def listar_versiones(id_situacion: int, usuario: Usuario) -> list[Version]:
    """Devuelve el historial de versiones ordenado descendentemente."""
    sa = obtener(id_situacion, usuario)
    return sorted(sa.versiones, key=lambda v: v.numero_version, reverse=True)
