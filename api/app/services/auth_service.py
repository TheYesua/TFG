"""Servicio de autenticación y registro de usuarios."""
from __future__ import annotations

from sqlalchemy import select

from ..extensions import db
from ..models import Rol, Usuario


class AuthError(Exception):
    """Error de autenticación / registro con tipo discriminado."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def registrar_usuario(
    *,
    correo: str,
    contrasena: str,
    nombre: str,
    centro_educativo: str | None = None,
    especialidad: str | None = None,
    comunidad_autonoma: str | None = None,
    rol_nombre: str = Rol.DOCENTE,
) -> Usuario:
    """Crea un nuevo usuario con el rol indicado (por defecto, docente).

    Lanza ``AuthError`` con código ``correo_duplicado`` o ``rol_inexistente``.
    """
    correo_normalizado = correo.lower().strip()

    existente = db.session.scalar(
        select(Usuario).where(Usuario.correo == correo_normalizado)
    )
    if existente is not None:
        raise AuthError("correo_duplicado", "Ya existe un usuario con ese correo")

    rol = db.session.scalar(select(Rol).where(Rol.nombre == rol_nombre))
    if rol is None:
        raise AuthError("rol_inexistente", f"No existe el rol {rol_nombre!r}")

    usuario = Usuario(
        id_rol=rol.id_rol,
        correo=correo_normalizado,
        nombre=nombre,
        centro_educativo=centro_educativo,
        especialidad=especialidad,
        comunidad_autonoma=comunidad_autonoma,
    )
    usuario.set_password(contrasena)

    db.session.add(usuario)
    db.session.commit()
    return usuario


def resetear_contrasena(*, correo: str, nueva_contrasena: str) -> Usuario:
    """Cambia la contraseña de un usuario identificado por correo.

    Lanza ``AuthError`` con código ``usuario_no_encontrado`` si el correo
    no existe en la base de datos.
    """
    correo_normalizado = correo.lower().strip()
    usuario = db.session.scalar(
        select(Usuario).where(Usuario.correo == correo_normalizado)
    )
    if usuario is None:
        raise AuthError("usuario_no_encontrado", "No existe ningún usuario con ese correo")

    usuario.set_password(nueva_contrasena)
    db.session.commit()
    return usuario


def autenticar(correo: str, contrasena: str) -> Usuario:
    """Devuelve el usuario si las credenciales son válidas, si no ``AuthError``.

    Por seguridad, devolvemos el mismo error tanto si el correo no existe como
    si la contraseña es incorrecta (evita enumeración de cuentas).
    """
    correo_normalizado = correo.lower().strip()

    usuario = db.session.scalar(
        select(Usuario).where(Usuario.correo == correo_normalizado)
    )
    if usuario is None or not usuario.check_password(contrasena):
        raise AuthError("credenciales_invalidas", "Correo o contraseña incorrectos")

    return usuario
