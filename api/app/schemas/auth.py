"""Schemas de entrada para los endpoints de autenticación."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterIn(BaseModel):
    """Datos requeridos para registrar un nuevo usuario."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    correo: EmailStr
    contrasena: str = Field(min_length=8, max_length=128)
    nombre: str = Field(min_length=2, max_length=100)
    centro_educativo: str | None = Field(default=None, max_length=200)
    especialidad: str | None = Field(default=None, max_length=100)
    comunidad_autonoma: str | None = Field(default=None, max_length=50)

    @field_validator("contrasena")
    @classmethod
    def _password_complejidad(cls, v: str) -> str:
        """Mínimo 8 chars, al menos una letra y un dígito."""
        if not any(c.isalpha() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un dígito")
        return v


class LoginIn(BaseModel):
    """Credenciales para iniciar sesión."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    correo: EmailStr
    contrasena: str = Field(min_length=1, max_length=128)


class ResetPasswordIn(BaseModel):
    """Datos para restablecer la contraseña directamente."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    correo: EmailStr
    nueva_contrasena: str = Field(min_length=8, max_length=128)

    @field_validator("nueva_contrasena")
    @classmethod
    def _password_complejidad(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("La contraseña debe contener al menos una letra")
        if not any(c.isdigit() for c in v):
            raise ValueError("La contraseña debe contener al menos un dígito")
        return v
