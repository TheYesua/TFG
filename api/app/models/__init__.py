"""Modelos SQLAlchemy del dominio.

Importar todos los modelos aquí garantiza que SQLAlchemy/Alembic los descubre
cuando se llama a ``db.create_all()`` o se autogenera una migración.
"""
from .rol import Rol
from .usuario import Usuario
from .curriculo import Competencia, CriterioEvaluacion, SaberBasico
from .ods import ODS
from .situacion import (
    SituacionAprendizaje,
    Version,
    situacion_competencia,
    situacion_criterio,
    situacion_saber,
    situacion_ods,
)

__all__ = [
    "Rol",
    "Usuario",
    "Competencia",
    "CriterioEvaluacion",
    "SaberBasico",
    "ODS",
    "SituacionAprendizaje",
    "Version",
    "situacion_competencia",
    "situacion_criterio",
    "situacion_saber",
    "situacion_ods",
]
