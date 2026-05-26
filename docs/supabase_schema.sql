-- =========================================================
-- Pariwana Hostels - Base inicial Supabase/PostgreSQL
-- =========================================================

create extension if not exists "uuid-ossp";

-- =========================
-- ENUMS
-- =========================

create type app_role as enum (
  'super_admin',
  'admin',
  'operador',
  'supervisor'
);

create type worker_status as enum (
  'activo',
  'inactivo',
  'cesado'
);

create type assignment_status as enum (
  'programado',
  'confirmado',
  'modificado',
  'anulado'
);

create type audit_action as enum (
  'create',
  'update',
  'delete',
  'export',
  'import',
  'login',
  'permission_change',
  'month_close'
);

-- =========================
-- TENANTS / SEDES
-- =========================

create table tenants (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  slug text not null unique,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table sites (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  slug text not null,
  city text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (tenant_id, slug)
);

create table areas (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  site_id uuid not null references sites(id) on delete cascade,
  name text not null,
  code text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (site_id, name)
);

-- =========================
-- USERS / PERMISSIONS
-- auth.users viene de Supabase Auth
-- =========================

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  tenant_id uuid references tenants(id) on delete set null,
  full_name text not null,
  email text not null,
  role app_role not null default 'operador',
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table user_site_permissions (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references profiles(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  site_id uuid not null references sites(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, site_id)
);

create table user_area_permissions (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references profiles(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  site_id uuid not null references sites(id) on delete cascade,
  area_id uuid not null references areas(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, area_id)
);

-- =========================
-- MODULES
-- =========================

create table modules (
  id uuid primary key default uuid_generate_v4(),
  code text not null unique,
  name text not null,
  description text,
  is_global boolean not null default false
);

create table tenant_modules (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  module_id uuid not null references modules(id) on delete cascade,
  is_enabled boolean not null default true,
  created_at timestamptz not null default now(),
  unique (tenant_id, module_id)
);

-- =========================
-- WORKERS
-- =========================

create table workers (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  site_id uuid not null references sites(id) on delete restrict,
  area_id uuid references areas(id) on delete set null,

  employee_code text,
  document_type text,
  document_number text not null,
  first_name text not null,
  last_name text not null,
  email text,
  phone text,

  buk_employee_id text,
  status worker_status not null default 'activo',

  hire_date date,
  termination_date date,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (tenant_id, document_number)
);

-- =========================
-- SHIFTS / SPECIAL STATES
-- =========================

create table shifts (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  site_id uuid references sites(id) on delete cascade,

  name text not null,
  code text not null,
  start_time time,
  end_time time,
  break_minutes integer not null default 0,
  total_minutes integer,

  is_night_shift boolean not null default false,
  is_active boolean not null default true,

  created_at timestamptz not null default now(),

  unique (tenant_id, code)
);

create table special_states (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,

  name text not null,
  code text not null,
  buk_code text,
  is_paid boolean not null default false,
  is_worked boolean not null default false,
  is_active boolean not null default true,

  created_at timestamptz not null default now(),

  unique (tenant_id, code)
);

-- =========================
-- SCHEDULE ASSIGNMENTS
-- =========================

create table schedule_assignments (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  site_id uuid not null references sites(id) on delete restrict,
  area_id uuid references areas(id) on delete set null,
  worker_id uuid not null references workers(id) on delete cascade,

  work_date date not null,
  shift_id uuid references shifts(id) on delete restrict,
  special_state_id uuid references special_states(id) on delete restrict,

  status assignment_status not null default 'programado',
  notes text,

  created_by uuid references profiles(id) on delete set null,
  updated_by uuid references profiles(id) on delete set null,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint assignment_requires_shift_or_state
    check (
      shift_id is not null
      or special_state_id is not null
    ),

  unique (tenant_id, worker_id, work_date)
);

-- =========================
-- BUK CONFIG / EXPORTS
-- =========================

create table buk_report_configs (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,

  name text not null,
  version text not null default 'v1',

  -- Se llenara despues de analizar la pestana "Reporte carga BUK"
  sheet_name text not null default 'Reporte carga BUK',
  header_row integer,
  data_start_row integer,

  column_mapping jsonb not null default '{}'::jsonb,
  static_values jsonb not null default '{}'::jsonb,
  validations jsonb not null default '{}'::jsonb,

  is_active boolean not null default true,
  created_at timestamptz not null default now(),

  unique (tenant_id, name, version)
);

create table buk_exports (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  site_id uuid references sites(id) on delete set null,

  config_id uuid references buk_report_configs(id) on delete restrict,

  period_start date not null,
  period_end date not null,

  file_name text,
  file_url text,

  generated_by uuid references profiles(id) on delete set null,
  generated_at timestamptz not null default now(),

  row_count integer not null default 0,
  validation_errors jsonb not null default '[]'::jsonb
);

-- =========================
-- MONTH CLOSE
-- =========================

create table month_closures (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  site_id uuid not null references sites(id) on delete cascade,

  period_year integer not null,
  period_month integer not null check (period_month between 1 and 12),

  closed_by uuid references profiles(id) on delete set null,
  closed_at timestamptz not null default now(),
  notes text,

  unique (tenant_id, site_id, period_year, period_month)
);

-- =========================
-- AUDIT LOG
-- =========================

create table audit_logs (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid references tenants(id) on delete set null,
  user_id uuid references profiles(id) on delete set null,

  action audit_action not null,
  module_code text,
  entity_table text,
  entity_id uuid,

  old_data jsonb,
  new_data jsonb,

  ip_address inet,
  user_agent text,

  created_at timestamptz not null default now()
);

-- =========================
-- UPDATED_AT TRIGGER
-- =========================

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger workers_set_updated_at
before update on workers
for each row execute function set_updated_at();

create trigger schedule_assignments_set_updated_at
before update on schedule_assignments
for each row execute function set_updated_at();

-- =========================
-- SEED DATA
-- =========================

insert into tenants (name, slug)
values ('Pariwana Hostels', 'pariwana')
on conflict (slug) do nothing;

insert into sites (tenant_id, name, slug, city)
select id, 'Pariwana Lima', 'lima', 'Lima'
from tenants
where slug = 'pariwana'
on conflict (tenant_id, slug) do nothing;

insert into sites (tenant_id, name, slug, city)
select id, 'Pariwana Cusco', 'cusco', 'Cusco'
from tenants
where slug = 'pariwana'
on conflict (tenant_id, slug) do nothing;

insert into modules (code, name) values
  ('workers', 'Trabajadores'),
  ('areas', 'Areas'),
  ('shifts', 'Turnos'),
  ('special_states', 'Estados Especiales'),
  ('schedule_assignments', 'Asignacion de Horarios'),
  ('next_15_days_control', 'Control proximos 15 dias'),
  ('buk_report', 'Reporte BUK'),
  ('buk_preview', 'Vista previa BUK'),
  ('buk_validator', 'Validador BUK'),
  ('users_permissions', 'Usuarios y permisos'),
  ('import_export', 'Importacion/Exportacion'),
  ('audit', 'Auditoria'),
  ('buk_config', 'Configuracion BUK'),
  ('month_close', 'Cierre de mes')
on conflict (code) do nothing;

insert into tenant_modules (tenant_id, module_id, is_enabled)
select t.id, m.id, true
from tenants t
cross join modules m
where t.slug = 'pariwana'
on conflict (tenant_id, module_id) do nothing;
