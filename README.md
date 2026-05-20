# Implementación — TFG

Backend de la aplicación de generación de Situaciones de Aprendizaje LOMLOE.

## Arquitectura

Despliegue mediante Docker Compose con cinco servicios principales más uno opcional para desarrollo:

| Servicio  | Puerto host          | Rol                                                       |
|-----------|----------------------|-----------------------------------------------------------|
| `nginx`   | `8080`               | Reverse proxy, único punto de entrada público             |
| `api`     | (interno)            | Flask + Gunicorn. Auth, CRUD, render Jinja                |
| `worker`  | (interno)            | Celery. Llamadas largas al LLM, exportaciones pesadas     |
| `postgres`| `5432`               | Persistencia                                              |
| `redis`   | (interno)            | Broker Celery + caché + sesiones server-side              |
| `adminer` | `8081` (perfil `dev`)| Cliente web para inspeccionar PostgreSQL                  |

## Requisitos previos

- Docker Desktop (Windows / macOS) o Docker Engine + Compose v2 (Linux).
- Una clave de OpenAI con acceso al modelo configurado en `OPENAI_MODEL`.

## Puesta en marcha (primera vez)

1. Copia el fichero de variables de entorno y ajústalo:
   ```powershell
   Copy-Item .env.example .env
   ```
   Genera una `SECRET_KEY` segura:
   ```powershell
   python -c "import secrets; Write-Host secrets.token_hex(32)"
   ```
   Y rellena `OPENAI_API_KEY` con tu clave.

2. Construye las imágenes:
   ```powershell
   docker compose build
   ```

3. Arranca los servicios (incluyendo Adminer, perfil `dev`):
   ```powershell
   docker compose --profile dev up -d
   ```

4. Verifica que todo está vivo:
   ```powershell
   curl http://localhost:8080/health
   ```
   Deberías obtener:
   ```json
   { "app": "ok", "database": "ok", "redis": "ok", "model": "gpt-5.4" }
   ```

5. Adminer queda disponible en <http://localhost:8081> (sistema: PostgreSQL, servidor: `postgres`, credenciales del `.env`).

## Comandos habituales

```powershell
# Ver logs en vivo de un servicio
docker compose logs -f api

# Reiniciar solo el api tras cambios
docker compose restart api

# Ejecutar tests
docker compose exec api pytest

# Abrir un shell en el contenedor del api
docker compose exec api bash

# Ejecutar migraciones (cuando existan)
docker compose exec api flask --app app db upgrade

# Probar la cola de Celery
docker compose exec api python -c "from app.celery_worker import ping; print(ping.delay().get(timeout=5))"

# Parar todo
docker compose --profile dev down

# Parar y borrar volúmenes (¡destruye la BD!)
docker compose --profile dev down -v
```

## Estructura del proyecto

```
implementacion/
├── docker-compose.yml
├── .env.example
├── nginx/
│   └── nginx.conf
└── api/
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── __init__.py        # factory create_app
        ├── config.py
        ├── extensions.py      # db, login, session, redis
        ├── celery_worker.py   # entrypoint del worker
        ├── api/
        │   ├── __init__.py    # registro de blueprints
        │   └── health.py
        ├── models/            # (Fase 1)
        ├── schemas/           # (Fase 1)
        ├── services/          # (Fase 2+)
        ├── tasks/             # (Fase 4)
        └── prompts/           # (Fase 4)
```

## Hoja de ruta

- [x] **Fase 0** — Andamiaje Docker, healthchecks, factory Flask
- [ ] **Fase 1** — Modelos SQLAlchemy + migraciones + seeds LOMLOE
- [ ] **Fase 2** — Auth con sesiones server-side y roles
- [ ] **Fase 3** — CRUD de situaciones de aprendizaje
- [ ] **Fase 4** — Generación con LLM vía Celery
- [ ] **Fase 5** — Adaptaciones curriculares (ACS / ACNS)
- [ ] **Fase 6** — Exportación PDF / DOCX
- [ ] **Fase 7** — Endurecimiento y observabilidad
