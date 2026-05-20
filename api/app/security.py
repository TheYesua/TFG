"""Utilidades de seguridad y autorización: decoradores de roles."""
from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import jsonify
from flask_login import current_user


def role_required(*roles: str) -> Callable:
    """Restringe el acceso a usuarios con uno de los roles indicados.

    El usuario debe estar autenticado. Si no lo está, devolvemos 401;
    si lo está pero su rol no coincide, devolvemos 403.
    """

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "no_autenticado"}), 401
            if current_user.rol is None or current_user.rol.nombre not in roles:
                return jsonify({"error": "permiso_denegado"}), 403
            return view(*args, **kwargs)

        return wrapper

    return decorator
