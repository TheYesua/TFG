# Currículo LOMLOE — Extracción y carga

Este directorio contiene las herramientas para transformar el currículo
oficial publicado en el BOE (Real Decreto 217/2022) en datos
estructurados que el sistema utilizará para asistir al docente.

## Fuentes

El RD 217/2022 (BOE-A-2022-4975) está descargado en formato XML en:

```
DOCUMENTACION/referencias/rd_217_2022.xml
```

## Workflow

```
┌──────────────────────┐    extractor.py      ┌──────────────────────┐
│ rd_217_2022.xml      │ ───────────────────▶ │ salida/*.json        │
│ (BOE oficial)        │                      │ (datos estructurados) │
└──────────────────────┘                      └──────────────────────┘
                                                        │
                                              revisión humana
                                                        │
                                                        ▼
                                              ┌──────────────────────┐
                                              │ flask seed curriculo │
                                              │ (carga en BD)        │
                                              └──────────────────────┘
```

1. **Extracción automática** (`extractor.py`): lee el XML del BOE y
   produce un JSON por cada `(materia, ciclo)` con la estructura de
   competencias específicas, criterios de evaluación y saberes básicos.

2. **Revisión humana**: el JSON producido se inspecciona y corrige
   manualmente si fuera necesario (errores de parsing, cabeceras
   atípicas, etc.).

3. **Carga en BD**: el comando `flask seed curriculo` lee el JSON
   revisado y lo persiste de forma idempotente.

## Materias incluidas en el alcance del TFG

| Etiqueta del proyecto | Materia oficial en el BOE |
|-----------------------|---------------------------|
| Tecnología            | "Tecnología y Digitalización" (1.º a 3.º) y "Tecnología" (4.º) |
| Lengua                | "Lengua Castellana y Literatura"                              |
| Matemáticas           | "Matemáticas"                                                  |
| Inglés                | "Lengua Extranjera"                                            |

## Ciclos según el RD 217/2022

El BOE agrupa competencias y saberes por ciclos, no por cursos
individuales:

- **Cursos de primero a tercero** → comunes a 1.º, 2.º y 3.º ESO
- **Curso de cuarto** → específicos de 4.º ESO

Esta agrupación se preserva en el modelo: las entidades
`Competencia`, `CriterioEvaluacion` y `SaberBasico` llevan un
`cursos_aplicables` (lista de cursos a los que pertenece el elemento).

## Uso

```bash
# Desde el host (recomendado)
docker compose exec api python -m app.curriculo.extractor \
    --xml /app/../../DOCUMENTACION/referencias/rd_217_2022.xml \
    --salida /app/../../implementacion/curriculo/salida
```

(Las rutas dentro del contenedor pueden ajustarse; ver el script.)

## Formato JSON producido

```json
{
  "materia": "Tecnología y Digitalización",
  "etapa": "ESO",
  "ciclo": "Cursos de primero a tercero",
  "cursos_aplicables": ["1º ESO", "2º ESO", "3º ESO"],
  "competencias_especificas": [
    {
      "codigo": "CE1",
      "descripcion": "Buscar y seleccionar información ...",
      "descriptores": ["CCL3", "STEM1", "CD1"]
    }
  ],
  "criterios_evaluacion": [
    {"codigo": "1.1", "competencia": "CE1", "descripcion": "..."},
    {"codigo": "1.2", "competencia": "CE1", "descripcion": "..."}
  ],
  "saberes_basicos": [
    {
      "bloque": "A. Proceso de resolución de problemas",
      "items": ["Identificación y formulación ...", "..."]
    }
  ]
}
```
