"""Endpoints para el usuario autenticado (perfil propio)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ..extensions import db
from ..schemas import UsuarioOut, UsuarioUpdateIn


bp = Blueprint("me", __name__, url_prefix="/me")


@bp.get("")
@login_required
def obtener_perfil():
    """Devuelve los datos del usuario actualmente autenticado (CU-09)."""
    return jsonify(UsuarioOut.from_model(current_user).model_dump(mode="json")), 200


@bp.put("")
@login_required
def actualizar_perfil():
    """Actualiza los campos editables del propio perfil (CU-09)."""
    data = UsuarioUpdateIn.model_validate(request.get_json(silent=True) or {})
    cambios = data.model_dump(exclude_unset=True)

    for atributo, valor in cambios.items():
        setattr(current_user, atributo, valor)

    db.session.commit()
    return jsonify(UsuarioOut.from_model(current_user).model_dump(mode="json")), 200
