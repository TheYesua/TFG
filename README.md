# AWEBO — Aplicación Web para Docentes

Generador de **Situaciones de Aprendizaje LOMLOE** asistido por IA.
TFG · Ingeniería Informática — Universidad de Granada.

Permite al profesorado de Secundaria crear, editar y exportar Situaciones de
Aprendizaje (SA) conformes al Real Decreto 217/2022, con generación automática
de las seis secciones del currículo (descripción, objetivos, conexión
curricular, secuencia de sesiones, evaluación y atención a la diversidad)
mediante un LLM, anclando los criterios y saberes al catálogo oficial.

> Repositorio: <https://github.com/TheYesua/TFG>

---

## Arquitectura

Despliegue mediante Docker Compose. Cinco servicios principales más uno
opcional para desarrollo:

| Servicio   | Puerto host           | Rol                                                       |
|------------|-----------------------|-----------------------------------------------------------|
| `nginx`    | `8080`                | Reverse proxy, único punto de entrada público             |
| `api`      | (interno)             | Flask + Gunicorn. Auth, CRUD, render Jinja                |
| `worker`   | (interno)             | Celery. Llamadas largas al LLM y exportaciones pesadas    |
| `postgres` | `5432`                | Persistencia                                              |
| `redis`    | (interno)             | Broker Celery + caché + sesiones server-side              |
| `adminer`  | `8081` (perfil `dev`) | Cliente web para inspeccionar PostgreSQL                  |

### Decisiones técnicas clave

- **No SPA**: HTML renderizado en servidor con **Jinja2** + JavaScript "vanilla"
  para hidratación. Reduce superficie de ataque y simplifica el modelo mental.
- **Sesiones server-side** en Redis (Flask-Session) en lugar de JWT.
- **Rate limiting** con Flask-Limiter respaldado por Redis. Clave por usuario
  autenticado o por IP.
- **Logging estructurado** con `structlog` (JSON en producción, texto coloreado
  en desarrollo). Cada petición lleva `X-Request-ID` que se propaga también a
  las tareas Celery vía signals.
- **IA pluggable** por interfaz `LLMProvider`: implementaciones `OpenAIProvider`
  (real) y `FakeProvider` (determinista, sin red, para tests).
- **Exportación**: PDF con WeasyPrint, DOCX con `python-docx`. Fuente fijada
  explícitamente (Calibri) en el OOXML para coherencia entre visualizadores.
- **Accesibilidad WCAG 2.1 AA**: paleta auditada (contraste AAA en texto
  principal), skip-link, foco visible, navegación por teclado, `prefers-
  reduced-motion`, marcado semántico con `aria-*`.

---

## Requisitos previos

- **Docker Desktop** (Windows/macOS) o **Docker Engine + Compose v2** (Linux).
- Clave de **OpenAI** con acceso al modelo configurado en `OPENAI_MODEL`
  (o `AI_PROVIDER=fake` si solo quieres probar el flujo sin consumir tokens).

---

## Puesta en marcha (primera vez)

1. **Clona el repositorio**:
   ```powershell
   git clone https://github.com/TheYesua/TFG.git
   cd TFG
   ```

2. **Configura variables de entorno**:
   ```powershell
   Copy-Item .env.example .env
   ```
   Edita `.env` y rellena al menos:
   - `SECRET_KEY` (genera una con
     `python -c "import secrets; print(secrets.token_hex(32))"`).
   - `OPENAI_API_KEY` con tu clave real
     (<https://platform.openai.com/api-keys>).
   - `POSTGRES_PASSWORD` con algo razonable.

3. **Construye e inicia** los servicios (perfil `dev` añade Adminer):
   ```powershell
   docker compose build
   docker compose --profile dev up -d
   ```

4. **Aplica migraciones** y **carga semillas** del currículo LOMLOE:
   ```powershell
   docker compose exec api flask --app app db upgrade
   docker compose exec api flask --app app seed-roles
   docker compose exec api flask --app app seed-ods
   docker compose exec api flask --app app seed-curriculo
   ```

5. **Verifica el estado**:
   ```powershell
   curl http://localhost:8080/health
   ```
   Debe devolver:
   ```json
   { "app": "ok", "database": "ok", "redis": "ok", "model": "gpt-4o-mini" }
   ```

6. Abre la app en <http://localhost:8080>. Adminer queda en
   <http://localhost:8081> (sistema: PostgreSQL, servidor: `postgres`,
   credenciales del `.env`).

---

## Comandos habituales

```powershell
# Ver logs en vivo
docker compose logs -f api
docker compose logs -f worker

# Reiniciar un servicio tras cambios
docker compose restart api

# Shell dentro de un contenedor
docker compose exec api bash

# Ejecutar la suite de pruebas (no se versiona, pero existe en local)
docker compose exec api pytest -q

# Probar la cola Celery
docker compose exec api python -c "from app.celery_worker import ping; print(ping.delay().get(timeout=5))"

# Crear una migración nueva tras modificar modelos
docker compose exec api flask --app app db migrate -m "descripcion del cambio"
docker compose exec api flask --app app db upgrade

# Parar todo
docker compose --profile dev down

# Parar y borrar volúmenes (¡destruye la BD!)
docker compose --profile dev down -v
```

---

## Estructura del proyecto

```
implementacion/
├── docker-compose.yml
├── docker-compose.override.yml      # ajustes locales de desarrollo
├── .env.example
├── nginx/
│   └── nginx.conf
├── postgres/
│   └── init/                        # scripts de inicialización SQL
├── curriculo/
│   └── salida/                      # JSON LOMLOE precompilado (semillas)
├── docs/
│   └── ACCESIBILIDAD.md
└── api/
    ├── Dockerfile
    ├── requirements.txt
    ├── pytest.ini
    ├── migrations/                  # Alembic
    └── app/
        ├── __init__.py              # factory create_app()
        ├── config.py                # Config / DevConfig / TestConfig
        ├── extensions.py            # db, login, session, redis, limiter
        ├── logging_config.py        # structlog + contextvars
        ├── middleware.py            # request-id, X-Request-ID
        ├── celery_app.py            # Celery + signals para request-id
        ├── celery_worker.py         # entrypoint del worker
        ├── errors.py                # handlers globales (JSON / HTML)
        ├── security.py              # hashing, helpers
        ├── cli.py                   # comandos flask (seeds, etc.)
        ├── ai/                      # LLMProvider + factory (openai/fake)
        ├── api/                     # blueprints REST (auth, me, situaciones…)
        ├── models/                  # SQLAlchemy: usuario, situacion, curriculo
        ├── schemas/                 # Pydantic (entrada/salida)
        ├── services/                # lógica de negocio (auth, situaciones, export)
        ├── tasks/                   # tareas Celery (generación IA)
        ├── prompts/                 # prompts por sección LOMLOE versionados
        ├── seeds/                   # carga inicial (roles, ODS, currículo)
        ├── curriculo/               # parser del catálogo LOMLOE
        ├── static/                  # css, js, imagenes, favicon
        └── templates/               # Jinja: páginas + exportación PDF
```

---

## Hoja de ruta

- [x] **Fase 0** — Andamiaje Docker, healthchecks, factory Flask
- [x] **Fase 1** — Modelos SQLAlchemy + migraciones + seeds LOMLOE
- [x] **Fase 2** — Auth con sesiones server-side y roles
- [x] **Fase 3** — CRUD de situaciones de aprendizaje
- [x] **Fase 4** — Generación con LLM vía Celery
- [x] **Fase 5** — Adaptaciones curriculares (ACS / ACNS)
- [x] **Fase 6** — Exportación PDF / DOCX
- [x] **Fase 7** — Endurecimiento y observabilidad
      *(rate limiting + structured logging integrados;
      backups y OpenAPI quedan como mejora futura)*
- [x] **Fase 8** — Frontend definitivo (paleta WCAG AA, Inter, Lucide,
      iconografía, logo y favicon propios, páginas de ayuda/accesibilidad/
      mapa web/404/error)

---

## Seguridad y privacidad

- Las claves y contraseñas viven exclusivamente en `.env` (fuera del repo).
- `.env.example` se versiona con **placeholders**, nunca con valores reales.
- Las contraseñas de usuario se guardan con `bcrypt`.
- El contenido generado por IA queda asociado al usuario propietario;
  cualquier acceso ajeno devuelve `404` (no `403`, para no filtrar la
  existencia del recurso).
- Las cookies de sesión se emiten con `HttpOnly`, `Secure` (en producción)
  y `SameSite=Lax`.

---

## Accesibilidad

El proyecto se desarrolla apuntando a **WCAG 2.1 nivel AA**. Detalles,
limitaciones conocidas y vía de contacto: [docs/ACCESIBILIDAD.md](docs/ACCESIBILIDAD.md)
y la página `/accesibilidad` de la propia aplicación.

---

## Licencia

Trabajo de Fin de Grado de Jesús José Cantero López. Uso académico.
