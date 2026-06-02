@echo off
set PYTHONPATH=C:\Users\frazz\OneDrive\Documentos\App de RRHH Pariwana\backend\.deps
set DATABASE_URL=sqlite:///C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/backend/test.sqlite3
set DEBUG=true
set ALLOWED_HOSTS=127.0.0.1,localhost
echo [Pariwana Scheduler] Aplicando migraciones...
"C:\Users\frazz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" manage.py migrate
if errorlevel 1 (
  echo [Pariwana Scheduler] Error al ejecutar migraciones. Abortando inicio.
  exit /b 1
)
echo [Pariwana Scheduler] Iniciando servidor local en 127.0.0.1:8000
"C:\Users\frazz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" manage.py runserver 127.0.0.1:8000 --noreload
