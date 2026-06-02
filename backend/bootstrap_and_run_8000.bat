@echo off
set PYTHONPATH=C:\Users\frazz\OneDrive\Documentos\App de RRHH Pariwana\backend\.deps
set DATABASE_URL=sqlite:///C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/backend/test.sqlite3
set DEBUG=true
set ALLOWED_HOSTS=127.0.0.1,localhost

if "%DEMO_PASSWORD%"=="" (
  set DEMO_PASSWORD=StrongPass123
)

echo [Pariwana Scheduler] Aplicando migraciones...
"C:\Users\frazz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" manage.py migrate
if errorlevel 1 (
  echo [Pariwana Scheduler] Error al ejecutar migraciones.
  exit /b 1
)

echo [Pariwana Scheduler] Cargando bootstrap demo local...
"C:\Users\frazz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" manage.py bootstrap_local_demo --password %DEMO_PASSWORD% --days 15
if errorlevel 1 (
  echo [Pariwana Scheduler] Error al ejecutar bootstrap demo.
  exit /b 1
)

echo [Pariwana Scheduler] Ejecutando preflight de seguridad...
"C:\Users\frazz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" manage.py security_preflight
if errorlevel 1 (
  echo [Pariwana Scheduler] Error en preflight de seguridad.
  exit /b 1
)

echo [Pariwana Scheduler] Ejecutando QA local...
"C:\Users\frazz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" manage.py qa_check_local
if errorlevel 1 (
  echo [Pariwana Scheduler] Error en QA local.
  exit /b 1
)

echo [Pariwana Scheduler] Generando readiness report...
"C:\Users\frazz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" manage.py phase4_readiness_report --bootstrap-demo-password %DEMO_PASSWORD% --run-local-qa --output-file docs/phase4_readiness_report_latest.md
if errorlevel 1 (
  echo [Pariwana Scheduler] Error al generar readiness report.
  exit /b 1
)

echo [Pariwana Scheduler] Iniciando servidor local en 127.0.0.1:8000
"C:\Users\frazz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" manage.py runserver 127.0.0.1:8000 --noreload
