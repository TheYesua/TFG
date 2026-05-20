"""Páginas HTML mínimas para probar el sistema desde el navegador.

Estas vistas devuelven HTML renderizado con Jinja. Las acciones (registro,
login, edición de perfil) se realizan vía ``fetch`` desde JavaScript contra
los endpoints JSON ya existentes (``/auth/...``, ``/me``).
"""
from __future__ import annotations

from flask import Blueprint, render_template


bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/login")
def login_page():
    return render_template("login.html")


@bp.get("/register")
def register_page():
    return render_template("register.html")


@bp.get("/perfil")
def perfil_page():
    return render_template("perfil.html")


@bp.get("/restablecer-contrasena")
def restablecer_contrasena_page():
    return render_template("restablecer_contrasena.html")


@bp.get("/situaciones")
def situaciones_listar_page():
    return render_template("situaciones/listar.html")


@bp.get("/situaciones/nueva")
def situaciones_nueva_page():
    return render_template("situaciones/nueva.html")


@bp.get("/situaciones/<int:id_situacion>")
def situaciones_detalle_page(id_situacion: int):
    return render_template("situaciones/detalle.html", id_situacion=id_situacion)


@bp.get("/ayuda")
def ayuda_page():
    return render_template("ayuda.html")


@bp.get("/mapa-web")
def mapa_web_page():
    return render_template("mapa_web.html")


@bp.get("/accesibilidad")
def accesibilidad_page():
    return render_template("accesibilidad.html")
