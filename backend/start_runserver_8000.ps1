$env:PYTHONPATH='C:\Users\frazz\OneDrive\Documentos\App de RRHH Pariwana\backend\.deps'
$env:DATABASE_URL='sqlite:///C:/Users/frazz/OneDrive/Documentos/App de RRHH Pariwana/backend/test.sqlite3'
$env:DEBUG='true'
$env:ALLOWED_HOSTS='127.0.0.1,localhost'
Set-Location 'C:\Users\frazz\OneDrive\Documentos\App de RRHH Pariwana\backend'
& 'C:\Users\frazz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' manage.py runserver 127.0.0.1:8000 --noreload *> local_8000_runserver.log
