"""Blueprint REST para Situaciones de Aprendizaje (CRUD + duplicar + versiones)."""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from ..schemas import (
    AdaptacionCreateIn,
    DuplicarIn,
    SituacionCreateIn,
    SituacionListItemOut,
    SituacionOut,
    SituacionUpdateIn,
    VersionOut,
)
from ..extensions import limiter
from ..services import exportacion_service as exp
from ..services import situacion_service as svc
from ..tasks import generacion as tareas_generacion
from ..tasks import encolar
from ..prompts import SECCIONES


bp = Blueprint("situaciones", __name__, url_prefix="/api/situaciones")


# ---------------------------------------------------------------------------
# Manejador de errores propio del blueprint
# ---------------------------------------------------------------------------


@bp.errorhandler(svc.SituacionError)
def _handle(exc: svc.SituacionError):
    return jsonify({"error": exc.code, "mensaje": str(exc)}), exc.http_status


# ---------------------------------------------------------------------------
# Listar y crear (CU-03)
# ---------------------------------------------------------------------------


@bp.get("")
@login_required
def listar():
    """Lista situaciones del usuario aplicando filtros opcionales."""
    incluir_adapt = request.args.get("incluir_adaptaciones", "true").lower() != "false"
    items = svc.listar(
        current_user,
        curso=request.args.get("curso"),
        materia=request.args.get("materia"),
        estado=request.args.get("estado"),
        q=request.args.get("q"),
        incluir_adaptaciones=incluir_adapt,
        limit=int(request.args.get("limit", 100)),
        offset=int(request.args.get("offset", 0)),
    )
    return (
        jsonify(
            [
                SituacionListItemOut.from_model(sa).model_dump(mode="json")
                for sa in items
            ]
        ),
        200,
    )


@bp.post("")
@login_required
def crear():
    """Crea una nueva situación de aprendizaje.

    Si se pasa ``?generar=true`` o ``{"generar": true}`` en el body, lanza
    adicionalmente la tarea Celery de generación y devuelve 202 con
    ``task_id``. En otro caso devuelve 201 con la SA creada en borrador.
    """
    body = request.get_json(silent=True) or {}
    # "generar" no forma parte del esquema de creación; lo extraemos aparte.
    generar_flag = bool(body.pop("generar", False)) or (
        request.args.get("generar", "false").lower() == "true"
    )
    data = SituacionCreateIn.model_validate(body)
    sa = svc.crear(current_user, data.model_dump())

    if not generar_flag:
        return jsonify(SituacionOut.from_model(sa).model_dump(mode="json")), 201

    async_result = encolar(
        tareas_generacion.generar_situacion_completa, sa.id_situacion
    )
    payload = SituacionOut.from_model(sa).model_dump(mode="json")
    payload["task_id"] = async_result.id
    return jsonify(payload), 202


# ---------------------------------------------------------------------------
# Operaciones sobre una situación concreta
# ---------------------------------------------------------------------------


@bp.get("/<int:id_situacion>")
@login_required
def obtener(id_situacion: int):
    sa = svc.obtener(id_situacion, current_user)
    return jsonify(SituacionOut.from_model(sa).model_dump(mode="json")), 200


@bp.put("/<int:id_situacion>")
@login_required
def actualizar(id_situacion: int):
    """Actualiza la situación. Crea automáticamente una versión histórica."""
    data = SituacionUpdateIn.model_validate(request.get_json(silent=True) or {})
    cambios = data.model_dump(exclude_unset=True)
    sa = svc.actualizar(id_situacion, current_user, cambios)
    return jsonify(SituacionOut.from_model(sa).model_dump(mode="json")), 200


@bp.delete("/<int:id_situacion>")
@login_required
def eliminar(id_situacion: int):
    svc.eliminar(id_situacion, current_user)
    return "", 204


# ---------------------------------------------------------------------------
# Duplicación
# ---------------------------------------------------------------------------


@bp.post("/<int:id_situacion>/duplicar")
@login_required
def duplicar(id_situacion: int):
    data = DuplicarIn.model_validate(request.get_json(silent=True) or {})
    copia = svc.duplicar(id_situacion, current_user, data.titulo)
    return jsonify(SituacionOut.from_model(copia).model_dump(mode="json")), 201


# ---------------------------------------------------------------------------
# Versiones (CU-07)
# ---------------------------------------------------------------------------


@bp.get("/<int:id_situacion>/versiones")
@login_required
def listar_versiones(id_situacion: int):
    versiones = svc.listar_versiones(id_situacion, current_user)
    return (
        jsonify(
            [
                VersionOut.model_validate(v, from_attributes=True).model_dump(
                    mode="json"
                )
                for v in versiones
            ]
        ),
        200,
    )


# ---------------------------------------------------------------------------
# Adaptaciones curriculares (CU-10)
# ---------------------------------------------------------------------------


@bp.post("/<int:id_situacion>/adaptaciones")
@login_required
def crear_adaptacion(id_situacion: int):
    """Crea una SA hija de adaptación y lanza su generación asíncrona (CU-10).

    Devuelve 202 + task_id. La SA adaptada queda en estado ``generando``
    hasta que la tarea Celery termine.
    """
    sa_origen = svc.obtener(id_situacion, current_user)

    data = AdaptacionCreateIn.model_validate(request.get_json(silent=True) or {})

    tipo_label = {"no_significativa": "ACNS", "significativa": "ACS"}[data.tipo_adaptacion]
    titulo_adapt = data.titulo or f"[{tipo_label}] {sa_origen.titulo}"

    sa_adapt = svc.crear(current_user, {
        "titulo": titulo_adapt,
        "curso": sa_origen.curso,
        "materia": sa_origen.materia,
        "comunidad_autonoma": sa_origen.comunidad_autonoma,
        "descripcion": sa_origen.descripcion,
        "metodologia": sa_origen.metodologia,
        "num_sesiones": sa_origen.num_sesiones,
        "duracion_sesion_minutos": sa_origen.duracion_sesion_minutos,
        "idioma": sa_origen.idioma,
        # perfil_aula de la SA hija = descripción del alumno concreto,
        # no el perfil de aula de origen (que se pasa por contenido_origen).
        "perfil_aula": data.perfil_alumnado,
        "materiales_contexto": sa_origen.materiales_contexto,
        # Metadatos de adaptación en el mismo commit para evitar estado inconsistente.
        "id_situacion_origen": sa_origen.id_situacion,
        "tipo_adaptacion": data.tipo_adaptacion,
        "perfil_alumnado": data.perfil_alumnado,
    })

    async_result = encolar(
        tareas_generacion.generar_situacion_completa, sa_adapt.id_situacion
    )
    payload = SituacionOut.from_model(sa_adapt).model_dump(mode="json")
    payload["task_id"] = async_result.id
    return jsonify(payload), 202


@bp.get("/<int:id_situacion>/adaptaciones")
@login_required
def listar_adaptaciones(id_situacion: int):
    """Lista todas las adaptaciones derivadas de una SA (CU-10)."""
    svc.obtener(id_situacion, current_user)  # valida permisos
    from ..extensions import db
    from ..models import SituacionAprendizaje as SAModel
    from sqlalchemy import select
    adaptaciones = db.session.scalars(
        select(SAModel).where(SAModel.id_situacion_origen == id_situacion)
    ).all()
    return (
        jsonify([
            SituacionListItemOut.from_model(a).model_dump(mode="json")
            for a in adaptaciones
        ]),
        200,
    )


# ---------------------------------------------------------------------------
# Generación IA (CU-03 / CU-05)
# ---------------------------------------------------------------------------


@bp.post("/<int:id_situacion>/generar")
@login_required
@limiter.limit("10 per hour")
def generar(id_situacion: int):
    """Lanza la generación asíncrona completa de la SA. Devuelve 202 + task_id."""
    sa = svc.obtener(id_situacion, current_user)
    if sa.estado == sa.GENERANDO:
        return (
            jsonify(
                {
                    "error": "ya_generando",
                    "mensaje": "La SA ya tiene una generación en curso.",
                }
            ),
            409,
        )

    async_result = encolar(
        tareas_generacion.generar_situacion_completa, id_situacion
    )
    return (
        jsonify(
            {
                "id_situacion": id_situacion,
                "task_id": async_result.id,
                "estado": sa.GENERANDO,
            }
        ),
        202,
    )


@bp.post("/<int:id_situacion>/regenerar/<seccion>")
@login_required
@limiter.limit("15 per hour")
def regenerar_seccion(id_situacion: int, seccion: str):
    """Regenera una única sección de la SA (CU-05)."""
    sa = svc.obtener(id_situacion, current_user)

    if seccion not in SECCIONES:
        return (
            jsonify(
                {
                    "error": "seccion_desconocida",
                    "mensaje": f"Secciones válidas: {sorted(SECCIONES)}",
                }
            ),
            400,
        )
    if sa.estado == sa.GENERANDO:
        return (
            jsonify(
                {
                    "error": "ya_generando",
                    "mensaje": "La SA ya tiene una generación en curso.",
                }
            ),
            409,
        )

    async_result = encolar(
        tareas_generacion.generar_seccion, id_situacion, seccion
    )
    return (
        jsonify(
            {
                "id_situacion": id_situacion,
                "seccion": seccion,
                "task_id": async_result.id,
                "estado": sa.GENERANDO,
            }
        ),
        202,
    )


# ---------------------------------------------------------------------------
# Exportación a PDF/DOCX (CU-06)
# ---------------------------------------------------------------------------


@bp.get("/<int:id_situacion>/exportar")
@login_required
@limiter.limit("20 per minute")
def exportar(id_situacion: int):
    """Exporta la SA en el formato indicado por ``?formato=pdf|docx``.

    Sólo permite exportar SA que ya tienen contenido generado. Si la
    SA está en borrador, devuelve 409.
    """
    formato = (request.args.get("formato") or "pdf").lower()
    if formato not in {"pdf", "docx"}:
        return (
            jsonify(
                {
                    "error": "formato_no_soportado",
                    "mensaje": "Formatos válidos: pdf, docx.",
                }
            ),
            400,
        )

    sa = svc.obtener(id_situacion, current_user)
    if not sa.contenido:
        return (
            jsonify(
                {
                    "error": "sin_contenido",
                    "mensaje": "La SA aún no tiene contenido generado.",
                }
            ),
            409,
        )

    if formato == "pdf":
        data = exp.renderizar_pdf(sa, current_user)
        mimetype = "application/pdf"
    else:  # docx
        data = exp.renderizar_docx(sa, current_user)
        mimetype = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    return Response(
        data,
        mimetype=mimetype,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{exp.nombre_fichero(sa, formato)}"'
            ),
        },
    )
