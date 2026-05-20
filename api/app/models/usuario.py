"""Entidad Usuario."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import bcrypt
from flask_login import UserMixin
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db

if TYPE_CHECKING:
    from .rol import Rol
    from .situacion import SituacionAprendizaje


class Usuario(db.Model, UserMixin):
    """Usuario registrado en el sistema (docente o administrador)."""

    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_rol: Mapped[int] = mapped_column(
        ForeignKey("rol.id_rol", ondelete="RESTRICT"), nullable=False, index=True
    )

    correo: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    contrasena_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    centro_educativo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    especialidad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    comunidad_autonoma: Mapped[str | None] = mapped_column(String(50), nullable=True)

    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ultima_sesion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    rol: Mapped["Rol"] = relationship(back_populates="usuarios", lazy="joined")
    situaciones: Mapped[list["SituacionAprendizaje"]] = relationship(
        back_populates="usuario",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    # ----- Flask-Login -----
    def get_id(self) -> str:  # noqa: D401
        """Identificador como string requerido por Flask-Login."""
        return str(self.id_usuario)

    # ----- Contraseñas -----
    def set_password(self, plain: str) -> None:
        """Genera y almacena el hash bcrypt de la contraseña en claro."""
        self.contrasena_hash = bcrypt.hashpw(
            plain.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, plain: str) -> bool:
        """Comprueba una contraseña contra el hash almacenado."""
        if not self.contrasena_hash:
            return False
        return bcrypt.checkpw(
            plain.encode("utf-8"), self.contrasena_hash.encode("utf-8")
        )

    def touch_last_seen(self) -> None:
        """Marca el momento del último acceso del usuario."""
        self.ultima_sesion = datetime.now(timezone.utc)

    # ----- Helpers de rol -----
    @property
    def es_administrador(self) -> bool:
        return self.rol is not None and self.rol.nombre == "administrador"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Usuario id={self.id_usuario} correo={self.correo!r}>"
