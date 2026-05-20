"""Extractor del currículo LOMLOE a partir de los XML del BOE.

Soporta dos fuentes oficiales, configurables como "perfiles":

* ``rd_217`` — Real Decreto 217/2022 (BOE-A-2022-4975), enseñanzas mínimas
  estatales. Estructura más sintética: criterios y saberes agrupados por
  ciclos amplios ("Cursos de primero a tercero" / "Curso de cuarto").
  Cubre 1.º a 3.º ESO para Matemáticas; no incluye Matemáticas 4.º.

* ``orden_efp_754`` — Orden EFP/754/2022 (BOE-A-2022-13172), desarrollo
  curricular en el ámbito de Ceuta y Melilla. Estructura más detallada:
  saberes organizados por curso individual ("Primer curso", "Segundo
  curso", ...) y Matemáticas 4.º está disponible en dos itinerarios
  (A y B), tratados como materias independientes.

Ambos perfiles producen el mismo formato de salida JSON, lo que permite
intercambiar la fuente sin tocar el resto del sistema.

Uso:

    docker compose exec api python -m app.curriculo.extractor \\
        --xml /tmp/orden_754.xml \\
        --perfil orden_efp_754 \\
        --salida /tmp/curriculo_salida
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from lxml import etree


logger = logging.getLogger("curriculo.extractor")


# ---------------------------------------------------------------------------
# Perfiles de extracción
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Perfil:
    """Configuración específica del formato de un BOE concreto."""

    nombre: str

    # Clase CSS que envuelve la cabecera de cada materia.
    clase_cabecera_materia: str

    # Si es True, la cabecera se compara en mayúsculas con el nombre oficial.
    cabecera_mayusculas: bool

    # Materias del scope del TFG (claves) -> etiqueta corta en la app (valores).
    materias_objetivo: dict[str, str]

    # Cursos por defecto si la materia no contiene marcadores de ciclo.
    cursos_por_defecto: dict[str, list[str]]


PERFIL_RD_217 = Perfil(
    nombre="rd_217",
    clase_cabecera_materia="centro_negrita",
    cabecera_mayusculas=False,
    materias_objetivo={
        "Tecnología y Digitalización": "Tecnología",   # 1.º-3.º ESO obligatoria
        "Tecnología": "Tecnología",                     # 4.º ESO opcional
        "Lengua Castellana y Literatura": "Lengua",
        "Matemáticas": "Matemáticas",
        "Lengua Extranjera": "Inglés",
    },
    cursos_por_defecto={
        "Tecnología y Digitalización": ["1º ESO", "2º ESO", "3º ESO"],
        "Tecnología": ["4º ESO"],
    },
)


PERFIL_ORDEN_EFP_754 = Perfil(
    nombre="orden_efp_754",
    clase_cabecera_materia="centro_redonda",
    cabecera_mayusculas=True,
    materias_objetivo={
        "TECNOLOGÍA Y DIGITALIZACIÓN": "Tecnología",
        "TECNOLOGÍA": "Tecnología",
        "LENGUA CASTELLANA Y LITERATURA": "Lengua",
        "MATEMÁTICAS": "Matemáticas",
        "LENGUA EXTRANJERA": "Inglés",
    },
    cursos_por_defecto={
        "TECNOLOGÍA Y DIGITALIZACIÓN": ["1º ESO", "2º ESO", "3º ESO"],
        "TECNOLOGÍA": ["4º ESO"],
    },
)


PERFILES = {
    PERFIL_RD_217.nombre: PERFIL_RD_217,
    PERFIL_ORDEN_EFP_754.nombre: PERFIL_ORDEN_EFP_754,
}


# Ordinales que aparecen en los marcadores de ciclo.
_ORDINALES = {
    "primero": 1, "segundo": 2, "tercero": 3, "cuarto": 4,
    "primer": 1, "segund": 2, "tercer": 3, "cuart": 4,
}


# ---------------------------------------------------------------------------
# Patrones de reconocimiento
# ---------------------------------------------------------------------------

# En la sección "Competencias específicas." cada CE empieza con
# "<N>. Texto..." (parrafo_2). Ej: "1. Buscar y seleccionar la información..."
RX_CE_INICIO = re.compile(r"^(\d+)\.\s+(.+)$", re.DOTALL)

# En la sección "Criterios de evaluación":  "Competencia específica N."
RX_CE_HEADER_CRIT = re.compile(r"^Competencia específica\s+(\d+)\.?\s*$")

# Línea de criterio: "1.1 Texto..." (con o sin punto final tras el código).
RX_CRITERIO = re.compile(r"^\s*(\d+)\.(\d+)\.?\s+(.+)$", re.DOTALL)

# Línea de descriptores del Perfil de salida.
RX_DESCRIPTORES = re.compile(
    r"descriptores del Perfil de salida\s*:\s*([^.]+)",
    re.IGNORECASE,
)

# Bloque de saberes: "A. Título del bloque."  (letra mayúscula + punto + texto)
RX_BLOQUE_SABER = re.compile(r"^([A-Z])\.\s+(.+?)\.?\s*$")

# Sub-encabezado numérico dentro de un bloque de saberes (Orden EFP/754):
# "1. Conteo." / "2. Cantidad." -> ignorar como item (es un agrupador).
RX_SUBENCAB_SABER = re.compile(r"^\d+\.\s+[A-ZÁÉÍÓÚÑa-záéíóúñ][^.]{0,40}\.?\s*$")

# Marcadores de ciclo: catálogo de patrones reconocidos.
# Cada entrada es (regex, fn que devuelve lista de cursos a partir de groups).
def _curso_uno(n: int) -> list[str]:
    return [f"{n}º ESO"]


def _curso_rango(ini: int, fin: int) -> list[str]:
    return [f"{i}º ESO" for i in range(ini, fin + 1)]


RX_CICLOS: list[tuple[re.Pattern[str], callable]] = [  # type: ignore[type-arg]
    # "Cursos de primero a tercero"
    (
        re.compile(r"^cursos?\s+de\s+(\w+)\s+a\s+(\w+)$"),
        lambda m: _curso_rango(_ORDINALES[m.group(1)], _ORDINALES[m.group(2)])
        if m.group(1) in _ORDINALES and m.group(2) in _ORDINALES else None,
    ),
    # "Cursos primero y segundo"
    (
        re.compile(r"^cursos?\s+(\w+)\s+y\s+(\w+)$"),
        lambda m: [f"{_ORDINALES[m.group(1)]}º ESO", f"{_ORDINALES[m.group(2)]}º ESO"]
        if m.group(1) in _ORDINALES and m.group(2) in _ORDINALES else None,
    ),
    # "Cuarto curso: Matemáticas A"  -> [4] (itinerario se extrae aparte)
    (
        re.compile(r"^(\w+)\s+curso\s*:\s*(.+)$"),
        lambda m: _curso_uno(_ORDINALES[m.group(1)]) if m.group(1) in _ORDINALES else None,
    ),
    # "Curso cuarto: Matemáticas B"
    (
        re.compile(r"^curso\s+(\w+)\s*:\s*(.+)$"),
        lambda m: _curso_uno(_ORDINALES[m.group(1)]) if m.group(1) in _ORDINALES else None,
    ),
    # "Primer curso" / "Cuarto curso"
    (
        re.compile(r"^(\w+)\s+curso$"),
        lambda m: _curso_uno(_ORDINALES[m.group(1)]) if m.group(1) in _ORDINALES else None,
    ),
    # "Curso de cuarto" / "Curso cuarto" / "Curso primero"
    (
        re.compile(r"^cursos?\s+(?:de\s+)?(\w+)$"),
        lambda m: _curso_uno(_ORDINALES[m.group(1)]) if m.group(1) in _ORDINALES else None,
    ),
]


# Itinerario A/B de Matemáticas 4.º (solo aparece en la Orden EFP/754).
RX_ITINERARIO_MATES = re.compile(
    r"matem[áa]ticas\s+([ab])\b",
    re.IGNORECASE,
)

# Catálogo de descriptores válidos (perfil de salida del Anexo I).
DESCRIPTORES_VALIDOS = {
    "CCL1", "CCL2", "CCL3", "CCL4", "CCL5",
    "CP1", "CP2", "CP3",
    "STEM1", "STEM2", "STEM3", "STEM4", "STEM5",
    "CD1", "CD2", "CD3", "CD4", "CD5",
    "CPSAA1", "CPSAA2", "CPSAA3", "CPSAA4", "CPSAA5",
    "CC1", "CC2", "CC3", "CC4",
    "CE1", "CE2", "CE3",
    "CCEC1", "CCEC2", "CCEC3", "CCEC4",
}


# ---------------------------------------------------------------------------
# Modelo intermedio
# ---------------------------------------------------------------------------


@dataclass
class CompetenciaEspecifica:
    codigo: str
    descripcion: str = ""
    descriptores: list[str] = field(default_factory=list)


@dataclass
class Criterio:
    codigo: str
    competencia: str
    descripcion: str


@dataclass
class BloqueSaberes:
    codigo: str
    titulo: str
    items: list[str] = field(default_factory=list)


@dataclass
class MateriaCiclo:
    materia_oficial: str   # Nombre oficial tal cual aparece en el BOE
    materia_corta: str     # Etiqueta usada en la app (ej. "Tecnología")
    ciclo: str             # Texto descriptivo del ciclo o "Único"
    cursos_aplicables: list[str]
    itinerario: str | None = None  # "A" o "B" para Matemáticas 4.º, None resto

    competencias: list[CompetenciaEspecifica] = field(default_factory=list)
    criterios: list[Criterio] = field(default_factory=list)
    saberes: list[BloqueSaberes] = field(default_factory=list)

    @property
    def materia_efectiva(self) -> str:
        """Nombre de la materia para la app, incluyendo itinerario si lo hay."""
        if self.itinerario:
            return f"{self.materia_corta} {self.itinerario}"
        return self.materia_corta

    def to_dict(self) -> dict:
        return {
            "materia_oficial": self.materia_oficial,
            "materia": self.materia_efectiva,
            "etapa": "ESO",
            "ciclo": self.ciclo,
            "itinerario": self.itinerario,
            "cursos_aplicables": self.cursos_aplicables,
            "competencias_especificas": [
                {
                    "codigo": c.codigo,
                    "descripcion": c.descripcion,
                    "descriptores": c.descriptores,
                }
                for c in self.competencias
            ],
            "criterios_evaluacion": [
                {
                    "codigo": cr.codigo,
                    "competencia": cr.competencia,
                    "descripcion": cr.descripcion,
                }
                for cr in self.criterios
            ],
            "saberes_basicos": [
                {
                    "codigo": b.codigo,
                    "bloque": f"{b.codigo}. {b.titulo}",
                    "titulo": b.titulo,
                    "items": b.items,
                }
                for b in self.saberes
            ],
        }


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _texto(p: etree._Element) -> str:
    return " ".join(p.itertext()).strip()


def _norm(t: str) -> str:
    return t.strip().rstrip(".").strip().lower()


def _es_marcador_competencias(t: str) -> bool:
    return _norm(t) == "competencias específicas"


def _es_marcador_criterios(t: str) -> bool:
    return _norm(t) == "criterios de evaluación"


def _es_marcador_saberes(t: str) -> bool:
    return _norm(t) == "saberes básicos"


def _parsear_ciclo(t: str) -> tuple[str, list[str], str | None] | None:
    """Reconoce un marcador de ciclo y devuelve ``(nombre, cursos, itinerario)``.

    El itinerario es "A" o "B" solo si el marcador menciona "Matemáticas A/B"
    (caso de la Orden EFP/754 para 4.º curso). En el resto de casos es None.
    """
    norm = _norm(t)
    # Pequeña optimización: si la palabra "curso" no aparece, no puede ser
    # un marcador de ciclo. Cubre todas las variantes ("Primer curso",
    # "Cursos de primero a tercero", "Cuarto curso: Matemáticas A", etc.).
    if "curso" not in norm:
        return None

    for regex, fn in RX_CICLOS:
        m = regex.match(norm)
        if m is None:
            continue
        cursos = fn(m)
        if cursos is None:
            continue
        # Detección del itinerario A/B si aparece en el marcador
        itinerario: str | None = None
        if len(m.groups()) >= 2:
            posible_itin = m.group(2)
            mi = RX_ITINERARIO_MATES.search(posible_itin or "")
            if mi:
                itinerario = mi.group(1).upper()
        return t.strip().rstrip("."), cursos, itinerario

    return None


def _extraer_descriptores(texto: str) -> list[str]:
    match = RX_DESCRIPTORES.search(texto)
    if not match:
        return []
    fragmento = match.group(1)
    codigos = re.findall(r"\b[A-Z]+\d+\b", fragmento)
    return [c for c in codigos if c in DESCRIPTORES_VALIDOS]


def _limpiar_item_saber(texto: str) -> str:
    """Quita el guion inicial (tipo '−', '–', '-', '—') y espacios."""
    return re.sub(r"^[\u2212\u2013\u2014\-]\s*", "", texto).strip()


# ---------------------------------------------------------------------------
# Iterador de párrafos
# ---------------------------------------------------------------------------


def _iter_parrafos(xml_path: Path) -> Iterator[tuple[str, str]]:
    tree = etree.parse(str(xml_path))
    texto_node = tree.getroot().find("texto")
    if texto_node is None:
        raise RuntimeError("El XML no contiene un nodo <texto>.")
    for p in texto_node.iter("p"):
        clase = p.get("class") or ""
        texto = _texto(p)
        if texto:
            yield clase, texto


# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------


_S_FUERA = "fuera"
_S_DESC_CE = "desc_ce"
_S_CRITERIOS = "criterios"
_S_SABERES = "saberes"


class _Parser:
    def __init__(self, perfil: Perfil) -> None:
        self.perfil = perfil
        self.resultados: list[MateriaCiclo] = []
        self.materia_oficial: str | None = None
        self.actual: MateriaCiclo | None = None
        self.estado: str = _S_FUERA
        self.ce_actual: CompetenciaEspecifica | None = None
        self.bloque_actual: BloqueSaberes | None = None

    # ---- helpers ---------------------------------------------------------

    def _cerrar_ce_actual(self) -> None:
        if self.ce_actual is not None and self.actual is not None:
            self.actual.competencias.append(self.ce_actual)
        self.ce_actual = None

    def _cerrar_bloque_actual(self) -> None:
        if self.bloque_actual is not None and self.actual is not None:
            # Si ya existe un bloque con el mismo código (caso típico:
            # los "sentidos" de Matemáticas que aparecen tres veces,
            # uno por curso del ciclo 1.º-3.º), fusionamos los items en
            # lugar de duplicar el bloque.
            existente = next(
                (b for b in self.actual.saberes if b.codigo == self.bloque_actual.codigo),
                None,
            )
            if existente is not None:
                existente.items.extend(self.bloque_actual.items)
            else:
                self.actual.saberes.append(self.bloque_actual)
        self.bloque_actual = None

    def _cerrar_ciclo_actual(self) -> None:
        if self.actual is not None:
            self._cerrar_ce_actual()
            self._cerrar_bloque_actual()
            self.resultados.append(self.actual)
        self.actual = None
        self.estado = _S_FUERA
        self.ce_actual = None
        self.bloque_actual = None

    def _abrir_materia(self, oficial: str) -> None:
        self._cerrar_ciclo_actual()
        self.materia_oficial = oficial
        self.actual = MateriaCiclo(
            materia_oficial=oficial,
            materia_corta=self.perfil.materias_objetivo[oficial],
            ciclo="Único",
            cursos_aplicables=list(
                self.perfil.cursos_por_defecto.get(
                    oficial, ["1º ESO", "2º ESO", "3º ESO", "4º ESO"]
                )
            ),
        )

    def _cambiar_ciclo(
        self,
        ciclo: str,
        cursos: list[str],
        itinerario: str | None,
    ) -> None:
        if self.materia_oficial is None or self.actual is None:
            return

        self._cerrar_ce_actual()
        self._cerrar_bloque_actual()

        competencias_heredadas = list(self.actual.competencias)

        # Descarta el ciclo "Único" si solo era contenedor de descripciones de CE
        if (
            self.actual.ciclo == "Único"
            and not self.actual.criterios
            and not self.actual.saberes
        ):
            pass
        else:
            self.resultados.append(self.actual)

        self.actual = MateriaCiclo(
            materia_oficial=self.materia_oficial,
            materia_corta=self.perfil.materias_objetivo[self.materia_oficial],
            ciclo=ciclo,
            cursos_aplicables=list(cursos),
            itinerario=itinerario,
            competencias=competencias_heredadas,
        )
        self.estado = _S_FUERA
        self.ce_actual = None
        self.bloque_actual = None

    # ---- detección de cabecera de materia --------------------------------

    def _es_cabecera_materia(self, clase: str, texto: str) -> str | None:
        """Si el párrafo es cabecera de una materia objetivo, devuelve la clave
        en ``perfil.materias_objetivo``; en caso contrario None."""
        if clase != self.perfil.clase_cabecera_materia:
            return None
        if texto in self.perfil.materias_objetivo:
            return texto
        return None

    def _es_cabecera_otra_materia(self, clase: str, texto: str) -> bool:
        """True si el párrafo es cabecera de una materia DISTINTA a las del
        scope. Sirve para cerrar la materia actual."""
        if clase != self.perfil.clase_cabecera_materia:
            return False
        # Heurística por perfil
        if self.perfil.cabecera_mayusculas:
            # Cabeceras de materia en mayúsculas, generalmente > 4 letras y
            # sin minúsculas. Evita falsos positivos como sub-secciones.
            if texto.isupper() and len(texto) > 4:
                # Excluir secciones genéricas que también van en mayúsculas
                excluidas = {
                    "CRITERIOS DE EVALUACIÓN", "SABERES BÁSICOS",
                    "COMPETENCIAS ESPECÍFICAS",
                }
                return texto not in excluidas
            return False
        else:
            # Perfil RD: cualquier centro_negrita con texto largo es candidata.
            return len(texto) > 4 and texto[0].isupper()

    # ---- procesamiento ---------------------------------------------------

    def procesar(self, clase: str, texto: str) -> None:  # noqa: C901
        # 1) Cabecera de materia (del scope)
        oficial = self._es_cabecera_materia(clase, texto)
        if oficial is not None:
            self._abrir_materia(oficial)
            return

        # 2) Cabecera de OTRA materia (fuera del scope) → cierra la actual
        if self.materia_oficial is not None and self._es_cabecera_otra_materia(clase, texto):
            self._cerrar_ciclo_actual()
            self.materia_oficial = None
            return

        if self.materia_oficial is None or self.actual is None:
            return

        # 2.5) Fin del contenido curricular de la materia. Después aparecen
        # comentarios metodológicos que incluyen sub-marcadores con la
        # palabra "curso" y nos descolocarían el parser.
        if _norm(texto).startswith("orientaciones metodológicas"):
            self._cerrar_ciclo_actual()
            self.materia_oficial = None
            return

        # 3) Marcador de ciclo
        ciclo_info = _parsear_ciclo(texto)
        if ciclo_info is not None:
            nombre, cursos, itin = ciclo_info
            # Caso especial: en la Orden EFP/754, los saberes de Matemáticas
            # 1.º-3.º se subdividen por curso individual ("Primer curso",
            # "Segundo curso", "Tercer curso") mientras los criterios son
            # comunes al ciclo. Si estamos en SABERES y el nuevo "ciclo"
            # propuesto está totalmente incluido en el ciclo actual, lo
            # tratamos como sub-encabezado (ignorado) en lugar de cambio.
            actual_set = set(self.actual.cursos_aplicables)
            nuevo_set = set(cursos)
            if (
                self.estado == _S_SABERES
                and itin is None
                and nuevo_set.issubset(actual_set)
                and nuevo_set != actual_set
            ):
                # Subdivisión interna: la ignoramos como marcador de ciclo
                # pero seguimos en SABERES acumulando los siguientes bloques
                # al ciclo actual.
                return
            self._cambiar_ciclo(nombre, cursos, itin)
            return

        # 4) Marcadores de sección
        if _es_marcador_competencias(texto):
            self._cerrar_ce_actual()
            self.estado = _S_DESC_CE
            return
        if _es_marcador_criterios(texto):
            self._cerrar_ce_actual()
            self.estado = _S_CRITERIOS
            return
        if _es_marcador_saberes(texto):
            self._cerrar_bloque_actual()
            self.estado = _S_SABERES
            return

        # 5) Contenido según estado
        if self.estado == _S_DESC_CE:
            self._procesar_descripcion_ce(texto)
        elif self.estado == _S_CRITERIOS:
            self._procesar_criterio(texto)
        elif self.estado == _S_SABERES:
            self._procesar_saber(texto)

    def _procesar_descripcion_ce(self, texto: str) -> None:
        descriptores = _extraer_descriptores(texto)
        if descriptores and self.ce_actual is not None:
            self.ce_actual.descriptores = descriptores
            return

        m = RX_CE_INICIO.match(texto)
        if m:
            num = m.group(1)
            descripcion = m.group(2).strip()
            self._cerrar_ce_actual()
            self.ce_actual = CompetenciaEspecifica(
                codigo=f"CE{num}",
                descripcion=descripcion,
            )

    def _procesar_criterio(self, texto: str) -> None:
        # Cabeceras "Competencia específica N." son visuales: las ignoramos.
        if RX_CE_HEADER_CRIT.match(texto):
            return
        m = RX_CRITERIO.match(texto)
        if m and self.actual is not None:
            ce = m.group(1)
            self.actual.criterios.append(
                Criterio(
                    codigo=f"{ce}.{m.group(2)}",
                    competencia=f"CE{ce}",
                    descripcion=m.group(3).strip(),
                )
            )

    def _procesar_saber(self, texto: str) -> None:
        # Bloque "A. Sentido numérico."
        m = RX_BLOQUE_SABER.match(texto)
        if m:
            self._cerrar_bloque_actual()
            self.bloque_actual = BloqueSaberes(
                codigo=m.group(1),
                titulo=m.group(2).strip(),
            )
            return

        # Sub-encabezado numérico ("1. Conteo.") → ignorado, no es item.
        if RX_SUBENCAB_SABER.match(texto):
            return

        if self.bloque_actual is not None:
            item = _limpiar_item_saber(texto)
            if item:
                self.bloque_actual.items.append(item)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def extraer(xml_path: Path, perfil: Perfil) -> list[MateriaCiclo]:
    parser = _Parser(perfil)
    for clase, texto in _iter_parrafos(xml_path):
        parser.procesar(clase, texto)
    parser._cerrar_ciclo_actual()
    return parser.resultados


# ---------------------------------------------------------------------------
# Volcado en disco
# ---------------------------------------------------------------------------


def _slugify(s: str) -> str:
    s = s.lower()
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}
    for k, v in reemplazos.items():
        s = s.replace(k, v)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def _nombre_fichero(mc: MateriaCiclo) -> str:
    """``matematicas__1_2_3.json``, ``matematicas_a__4.json``, etc."""
    base = _slugify(mc.materia_efectiva)
    digitos = []
    for c in mc.cursos_aplicables:
        m = re.match(r"(\d)", c)
        if m:
            digitos.append(m.group(1))
    suf = "_".join(digitos) if digitos else "unico"
    return f"{base}__{suf}.json"


def volcar(resultados: list[MateriaCiclo], salida: Path) -> list[Path]:
    salida.mkdir(parents=True, exist_ok=True)
    rutas: list[Path] = []
    for mc in resultados:
        ruta = salida / _nombre_fichero(mc)
        ruta.write_text(
            json.dumps(mc.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rutas.append(ruta)
    return rutas


def resumen(resultados: list[MateriaCiclo]) -> str:
    lineas = []
    for mc in resultados:
        cursos = ", ".join(mc.cursos_aplicables)
        itin = f" [{mc.itinerario}]" if mc.itinerario else ""
        lineas.append(
            f"  {mc.materia_efectiva:18s}{itin:5s} ({mc.materia_oficial:34s})  "
            f"CE={len(mc.competencias):2d}  CR={len(mc.criterios):3d}  "
            f"BL={len(mc.saberes):2d}   [{cursos}]"
        )
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Extrae el currículo LOMLOE del XML del BOE a JSON."
    )
    p.add_argument("--xml", required=True, type=Path)
    p.add_argument("--salida", required=True, type=Path)
    p.add_argument(
        "--perfil",
        choices=sorted(PERFILES.keys()),
        default=PERFIL_ORDEN_EFP_754.nombre,
        help="Formato del documento de entrada (default: orden_efp_754).",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s | %(message)s",
    )

    if not args.xml.exists():
        logger.error("No existe el XML de entrada: %s", args.xml)
        return 2

    perfil = PERFILES[args.perfil]
    logger.info("Procesando XML %s con perfil %s", args.xml, perfil.nombre)
    resultados = extraer(args.xml, perfil)
    if not resultados:
        logger.warning("No se extrajo ninguna materia.")
        return 1

    print("\nResumen de extracción:")
    print(resumen(resultados))

    rutas = volcar(resultados, args.salida)
    print(f"\n✓ Generados {len(rutas)} fichero(s) JSON en {args.salida}:")
    for r in rutas:
        print(f"   - {r.name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
