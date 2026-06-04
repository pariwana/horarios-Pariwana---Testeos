# Netlify + Supabase Setup

Este documento deja claro como conectar una version frontend en Netlify con Supabase sin exponer credenciales sensibles.

## 1. Ejecutar el query

En Supabase:

1. Abrir `SQL Editor`.
2. Crear un nuevo query.
3. Pegar y ejecutar el contenido de:
   - `docs/supabase_netlify_schema.sql`

Ese script crea:

- Tablas operativas de Pariwana.
- Tenant inicial `Pariwana Hostels`.
- Sedes iniciales `Pariwana Lima` y `Pariwana Cusco`.
- Modulos iniciales activos.
- Perfiles de rol base.
- Configuracion BUK inicial.
- Row Level Security.
- Policies para usuarios autenticados.
- Buckets privados para importaciones y exportaciones BUK.

## 2. Variables en Netlify

En Netlify, configurar solo variables seguras para navegador:

```env
VITE_SUPABASE_URL=https://TU_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=TU_ANON_KEY
```

No colocar en Netlify frontend:

```env
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_DB_PASSWORD
DATABASE_URL
```

La clave `service_role` solo debe vivir en un backend seguro o en funciones server-side privadas.

## 3. Auth redirects en Supabase

Esto no se configura con SQL. Debe configurarse en el panel de Supabase:

`Authentication > URL Configuration`

Valores recomendados:

```text
Site URL:
https://TU-SITIO.netlify.app

Redirect URLs:
https://TU-SITIO.netlify.app/*
http://localhost:5173/*
http://localhost:8000/*
```

## 4. Consideracion importante sobre Django

La app actual del repositorio es principalmente Django con templates. Si se despliega asi en produccion, Netlify no debe conectarse directo a la base de datos. El flujo recomendado seria:

```text
Netlify frontend -> Backend Django desplegado -> Supabase PostgreSQL
```

En ese caso, la base se debe crear ejecutando migraciones Django contra el `DATABASE_URL` de Supabase:

```bash
python manage.py migrate
python manage.py bootstrap_local_demo
python manage.py create_super_admin
```

El archivo `supabase_netlify_schema.sql` sirve para un camino alternativo: frontend en Netlify usando Supabase Auth y Supabase API directamente.

