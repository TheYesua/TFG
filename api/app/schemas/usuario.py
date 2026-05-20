"""Schemas Pydantic relacionados con la entidad Usuario."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UsuarioOut(BaseModel):
    """Representación pública del usuario (no expone hash de contraseña)."""

    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    correo: EmailStr
    nombre: str
    centro_educativo: str | None = None
    especialidad: str | None = None
    comunidad_autonoma: str | None = None
    fecha_registro: datetime
    ultima_sesion: datetime | None = None
    rol: str = Field(description="Nombre del rol del usuario")

    @classmethod
    def from_model(cls, usuario) -> "UsuarioOut":
        """Construye desde un objeto SQLAlchemy ``Usuario`` aplanando el rol."""
        return cls(
            id_usuario=usuario.id_usuario,
            correo=usuario.correo,
            nombre=usuario.nombre,
            centro_educativo=usuario.centro_educativo,
            especialidad=usuario.especialidad,
            comunidad_autonoma=usuario.comunidad_autonoma,
            fecha_registro=usuario.fecha_registro,
            ultima_sesion=usuario.ultima_sesion,
            rol=usuario.rol.nombre,
        )


class UsuarioUpdateIn(BaseModel):
    """Campos editables por el propio usuario en su perfil."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    centro_educativo: str | None = Field(default=None, max_length=200)
    especialidad: str | None = Field(default=None, max_length=100)
    comunidad_autonoma: str | None = Field(default=None, max_length=50)
