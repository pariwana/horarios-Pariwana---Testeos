# Pariwana BUK Scheduler

Aplicación interna de **Pariwana Hostels** para la gestión de horarios y generación del reporte de carga de turnos para **BUK**.

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Django 5 + Django REST Framework |
| Frontend | Django Templates + HTMX |
| Base de datos | PostgreSQL 16 |
| Exportación | OpenPyXL (XLSX) |
| Reportes | ReportLab (PDF) |
| Proxy | Nginx Proxy Manager |
| Contenedores | Docker + Docker Compose |

---

##  Arquitectura

```
Usuario → Nginx Proxy Manager (npm_network) → Django (Gunicorn) → PostgreSQL
```

- El servidor corre **Nginx Proxy Manager** con una red externa llamada `npm_network`.
- El contenedor de Django se conecta a `npm_network` y es accesible por el proxy.
- La base de datos PostgreSQL es externa (recomendado: Supabase).

---

##  Estructura del proyecto

```
.
├── backend/
│   ├── apps/                  # Aplicaciones Django
│   │   ├── audit/             # Auditoría
│   │   ├── buk_exports/       # Exportación BUK XLSX
│   │   ├── common/            # Utilidades comunes (permisos, helpers)
│   │   ├── imports/           # Importación de Excel
│   │   ├── modules/           # Activación de módulos
│   │   ├── month_closure/     # Cierre de mes
│   │   ├── scheduling/        # Asignación de horarios
│   │   ├── tenants/           # Multi-tenant
│   │   ├── users/             # Usuarios, roles y permisos
│   │   ├── webui/             # Interfaz web (templates + HTMX)
│   │   └── workers/           # Trabajadores
│   ├── config/                # Configuración Django (settings, urls, wsgi, asgi)
│   ├── templates/             # Templates HTML
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   └── manage.py
├── docs/                      # Documentación técnica
├── public/                    # Archivos estáticos para frontend desacoplado
├── .env.example               # Template de variables de entorno
├── docker-compose.yml         # Docker Compose para desarrollo
├── docker-compose.prod.yml    # Docker Compose para producción
├── requirements.txt           # Dependencias Python
└── netlify.toml               # Configuración Netlify (frontend alternativo)
```

---

##  Variables de entorno

Solo estas variables se usan realmente. Referencia cruzada: `backend/config/settings.py` + `backend/docker-entrypoint.sh`.

| Variable | Obligatoria | Uso |
|----------|------------|-----|
| `SECRET_KEY` | ✅ | Clave secreta de Django |
| `DEBUG` | ✅ | `False` en producción |
| `ENVIRONMENT` | ❌ (default `development`) | Entorno actual |
| `ALLOWED_HOSTS` | ✅ | Hosts/dominios permitidos (separados por coma) |
| `DATABASE_URL` | ✅ | URL completa de PostgreSQL |
| `DIRECT_URL` | ❌ | Conexión directa a PostgreSQL (sin PgBouncer) |
| `TIME_ZONE` | ❌ (default `America/Lima`) | Zona horaria |
| `BUK_EXPORT_DEFAULT_FORMAT` | ❌ (default `xlsx`) | Formato de exportación BUK |
| `BUK_DEFAULT_SHEET_NAME` | ❌ (default `Reporte carga BUK`) | Nombre de hoja del XLSX |

---

##  Setup local

### Requisitos

- Python 3.12+
- Docker + Docker Compose
- PostgreSQL 15+ (si no usas Docker)

### Con Docker (recomendado)

```bash
cp .env.example .env
# Editar .env con tus credenciales
docker compose up -d
```

### Sin Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cp backend/.env.example backend/.env
# Editar backend/.env (backend lee su propio .env, no el raíz)

python manage.py migrate
python manage.py create_initial_super_admin --email admin@pariwana.com --password <password>
python manage.py seed_initial_pariwana
python manage.py seed_demo_cusco_data --days 15
python manage.py runserver
```

### Bootstrap rápido

```bash
python manage.py bootstrap_local_demo --password StrongPass123 --days 15
```

---

##  Despliegue automático (GitHub Actions)

El proyecto incluye un pipeline de CI/CD en `.github/workflows/deploy.yml` con 3 jobs secuenciales:

1. **test** → `makemigrations --check` + tests automatizados.
2. **build** → sincroniza archivos al servidor via rsync y construye la imagen Docker.
3. **deploy** → levanta el contenedor, ejecuta health check y limpia recursos viejos.

Cada job es independiente: si uno falla, los siguientes se cancelan, y los logs muestran exactamente dónde falló.

###  Secretos requeridos en GitHub

Configurar estos secretos en `Settings > Secrets and variables > Actions`:

| Secreto | Descripción |
|---------|-------------|
| `SSH_PRIVATE_KEY` | Clave privada SSH para conectarse al servidor |
| `SSH_HOST` | IP o dominio del servidor |
| `SSH_USER` | Usuario SSH (ej: `deploy` o `root`) |
| `SSH_PORT` | Puerto SSH (opcional, default `22`) |
| `DEPLOY_ENV_FILE` | Contenido completo del archivo `.env` en una sola variable multi-línea |

###  `DEPLOY_ENV_FILE`

Este secreto debe contener el contenido **completo** del archivo `.env` de producción. Ejemplo:

```env
SECRET_KEY=<generar clave única>
DEBUG=False
ENVIRONMENT=production
ALLOWED_HOSTS=.tudominio.com,localhost
# Usar puerto 5432 directo (sin PgBouncer). NO usar ?pgbouncer=true
DATABASE_URL=postgresql://usuario:password@host:5432/pariwana_buk?sslmode=require
DIRECT_URL=
TIME_ZONE=America/Lima
BUK_EXPORT_DEFAULT_FORMAT=xlsx
BUK_DEFAULT_SHEET_NAME=Reporte carga BUK
```

> ⚠️ **Nunca incluir el `.env` real en el repositorio.** Usar GitHub Secrets.

---

##  Despliegue manual

```bash
# En el servidor
git clone <repo-url> /home/ubuntu/schedules
cd /home/ubuntu/schedules
cp .env.example .env
# Editar .env con valores de producción

docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

### Nginx Proxy Manager

1. Agregar un nuevo Proxy Host en NPM.
2. Domain: `tudominio.com`
3. Forward Hostname: `pariwana_scheduler_web`
4. Forward Port: `8000`
5. Scheme: `http`
6. SSL: Solicitar certificado Let's Encrypt.

---

##  Módulos del sistema

| Módulo | Descripción |
|--------|-------------|
| Tenants | Multi-tenant (Pariwana Hostels) |
| Sedes | Pariwana Lima, Pariwana Cusco |
| Usuarios y permisos | Roles: super_admin, admin, operator, supervisor |
| Trabajadores | Gestión de empleados por sede y área |
| Turnos | Definición de turnos con código BUK |
| Asignación de horarios | Calendario de asignación por trabajador |
| Exportación BUK | Generación de XLSX para carga en BUK |
| Importación Excel | Carga masiva desde Excel |
| Control 15 días | Vista de control de próximos 15 días |
| Cierre de mes | Bloqueo/reapertura de meses |
| Auditoría | Trazabilidad de acciones críticas |

---

##  Comandos útiles

```bash
# Backend
python manage.py makemigrations --check   # Verificar migraciones
python manage.py migrate                   # Aplicar migraciones
python manage.py test                      # Ejecutar tests
python manage.py collectstatic              # Recopilar archivos estáticos
python manage.py security_preflight        # Verificar seguridad
python manage.py phase4_readiness_report   # Reporte de readiness

# Frontend (si se usa React desacoplado)
npm install
npm run dev
npm run build
npm test
```

---

##  Documentación adicional

- [Setup local](docs/setup.md)
- [Formato de exportación BUK](docs/buk_export_format.md)
- [Producción y operación](docs/production.md)
- [Modelo de base de datos](docs/database_schema.md)
- [Permisos](docs/permissions.md)
- [Netlify + Supabase](docs/netlify_supabase_setup.md)

---

##  Licencia

Uso interno - Pariwana Hostels
