"""Comandos CLI personalizados expuestos vía ``flask <grupo> <comando>``."""
from __future__ import annotations

import click
from flask import Flask
from flask.cli import AppGroup


seed_cli = AppGroup("seed", help="Carga datos iniciales en la base de datos.")


@seed_cli.command("roles")
def cmd_seed_roles() -> None:
    """Inserta los roles del sistema (docente, administrador)."""
    from .seeds import seed_roles

    result = seed_roles()
    click.echo(
        f"[seed:roles] creados={result['creados']} actualizados={result['actualizados']}"
    )


@seed_cli.command("ods")
def cmd_seed_ods() -> None:
    """Inserta los 17 Objetivos de Desarrollo Sostenible."""
    from .seeds import seed_ods

    result = seed_ods()
    click.echo(
        f"[seed:ods] creados={result['creados']} actualizados={result['actualizados']}"
    )


@seed_cli.command("curriculo")
@click.option(
    "--directorio",
    "-d",
    default=None,
    help="Directorio con los JSON del extractor (por defecto /curriculo/salida).",
)
def cmd_seed_curriculo(directorio: str | None) -> None:
    """Carga competencias, criterios y saberes desde los JSON del extractor."""
    from pathlib import Path

    from .seeds import seed_curriculo

    ruta = Path(directorio) if directorio else None
    result = seed_curriculo(ruta)
    click.echo(
        f"[seed:curriculo] ficheros={result['ficheros']} "
        f"ce_nuevas={result['ce_nuevas']} ce_actualizadas={result['ce_actualizadas']} "
        f"cr_nuevos={result['cr_nuevos']} sb_nuevos={result['sb_nuevos']}"
    )


@seed_cli.command("all")
def cmd_seed_all() -> None:
    """Ejecuta todos los seeds disponibles en orden."""
    from .seeds import seed_roles, seed_ods, seed_curriculo

    r = seed_roles()
    click.echo(f"[seed:roles] creados={r['creados']} actualizados={r['actualizados']}")
    o = seed_ods()
    click.echo(f"[seed:ods] creados={o['creados']} actualizados={o['actualizados']}")
    c = seed_curriculo()
    click.echo(
        f"[seed:curriculo] ficheros={c['ficheros']} "
        f"ce_nuevas={c['ce_nuevas']} ce_actualizadas={c['ce_actualizadas']} "
        f"cr_nuevos={c['cr_nuevos']} sb_nuevos={c['sb_nuevos']}"
    )


def register_cli(app: Flask) -> None:
    """Registra todos los grupos de comandos CLI en la aplicación."""
    app.cli.add_command(seed_cli)
