-- =========================================================
-- Pariwana BUK Scheduler - Supabase schema for Netlify clients
-- =========================================================
-- Run this file in the Supabase SQL Editor.
--
-- Purpose:
-- - Create the operational database for Pariwana scheduling.
-- - Seed the initial tenant, properties and modules.
-- - Configure grants and Row Level Security for a Netlify frontend.
--
-- Important:
-- - This schema is for a Supabase-first frontend using Supabase Auth.
-- - If the Django backend is the production API, prefer running Django
--   migrations against the Supabase PostgreSQL DATABASE_URL instead.
-- - Never expose the Supabase service_role key in Netlify frontend code.
-- - Run this on a clean Supabase public schema. If an older experimental
--   Pariwana schema was already executed, back it up and reset/migrate it
--   intentionally before running this file.

begin;

-- =========================
-- EXTENSIONS
-- =========================

create extension if not exists pgcrypto;

-- =========================
-- ENUMS
-- =========================

do $$
begin
  if not exists (select 1 from pg_type where typname = 'tenant_status') then
    create type public.tenant_status as enum ('active', 'inactive');
  end if;

  if not exists (select 1 from pg_type where typname = 'app_role') then
    create type public.app_role as enum ('super_admin', 'admin', 'operator', 'supervisor');
  end if;

  if not exists (select 1 from pg_type where typname = 'import_batch_status') then
    create type public.import_batch_status as enum ('preview', 'confirmed', 'cancelled', 'failed');
  end if;

  if not exists (select 1 from pg_type where typname = 'month_closure_status') then
    create type public.month_closure_status as enum ('open', 'closed');
  end if;
end $$;

alter type public.app_role add value if not exists 'super_admin';
alter type public.app_role add value if not exists 'admin';
alter type public.app_role add value if not exists 'operator';
alter type public.app_role add value if not exists 'supervisor';

-- =========================
-- CORE TABLES
-- =========================

create table if not exists public.tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  slug text not null unique,
  status public.tenant_status not null default 'active',
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.properties (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  name text not null,
  slug text not null,
  location text not null default '',
  status public.tenant_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, slug),
  unique (tenant_id, name)
);

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  tenant_id uuid references public.tenants(id) on delete set null,
  email text not null unique,
  first_name text not null default '',
  last_name text not null default '',
  is_active boolean not null default true,
  is_staff boolean not null default false,
  is_super_admin boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.role_profiles (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  code text not null,
  name text not null,
  base_role public.app_role not null,
  description text not null default '',
  permissions jsonb not null default '{}'::jsonb,
  is_system boolean not null default false,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, code)
);

create table if not exists public.user_tenant_roles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  role public.app_role not null,
  role_profile_id uuid references public.role_profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, tenant_id)
);

create table if not exists public.module_activations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  module_key text not null,
  is_enabled boolean not null default true,
  enabled_by uuid references public.profiles(id) on delete set null,
  enabled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, module_key)
);

create table if not exists public.areas (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  name text not null,
  type text not null default '',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, property_id, name)
);

create table if not exists public.user_property_permissions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  can_access boolean not null default true,
  can_schedule boolean not null default false,
  can_export_buk boolean not null default false,
  can_manage_workers boolean not null default false,
  can_manage_shifts boolean not null default false,
  can_manage_areas boolean not null default false,
  can_manage_users boolean not null default false,
  can_view_reports boolean not null default false,
  can_use_control boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, tenant_id, property_id)
);

create table if not exists public.user_area_permissions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  area_id uuid not null references public.areas(id) on delete cascade,
  can_view boolean not null default true,
  can_schedule boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, tenant_id, property_id, area_id)
);

create table if not exists public.workers (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  document_number text not null,
  first_name text not null,
  last_name text not null,
  area_id uuid not null references public.areas(id) on delete restrict,
  active boolean not null default true,
  start_date date,
  end_date date,
  buk_employee_code text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, property_id, document_number)
);

create table if not exists public.shifts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  area_id uuid not null references public.areas(id) on delete restrict,
  name text not null,
  buk_code text not null,
  start_time time not null,
  end_time time not null,
  break_start time,
  break_end time,
  is_night_shift boolean not null default false,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, property_id, area_id, name),
  unique (tenant_id, property_id, buk_code)
);

create table if not exists public.special_states (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  name text not null,
  buk_code text not null default '',
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, property_id, name)
);

create table if not exists public.schedule_assignments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  worker_id uuid not null references public.workers(id) on delete cascade,
  work_date date not null,
  shift_id uuid references public.shifts(id) on delete restrict,
  special_state_id uuid references public.special_states(id) on delete restrict,
  created_by uuid references public.profiles(id) on delete set null,
  updated_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint schedule_assignment_one_value check (
    (shift_id is not null and special_state_id is null)
    or (shift_id is null and special_state_id is not null)
  ),
  unique (worker_id, property_id, work_date)
);

create table if not exists public.schedule_pattern_templates (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  area_id uuid references public.areas(id) on delete set null,
  name text not null,
  pattern jsonb not null default '{}'::jsonb,
  active boolean not null default true,
  created_by uuid references public.profiles(id) on delete set null,
  updated_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, property_id, area_id, name)
);

create table if not exists public.schedule_range_templates (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  area_id uuid references public.areas(id) on delete set null,
  name text not null,
  ranges jsonb not null default '[]'::jsonb,
  active boolean not null default true,
  created_by uuid references public.profiles(id) on delete set null,
  updated_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, property_id, area_id, name)
);

-- =========================
-- BUK / IMPORTS / CONTROL
-- =========================

create table if not exists public.buk_export_configs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  sheet_name text not null default 'Reporte carga BUK',
  date_format text not null default '%d-%m-%Y',
  include_area boolean not null default true,
  include_worker_name boolean not null default true,
  document_column_name text not null default 'RUT',
  name_column_name text not null default 'Nombre',
  area_column_name text not null default 'Area',
  header_row integer not null default 2,
  first_data_row integer not null default 3,
  export_format text not null default 'xlsx',
  other_settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, property_id)
);

create table if not exists public.buk_export_logs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  date_from date not null,
  date_to date not null,
  generated_by uuid references public.profiles(id) on delete set null,
  generated_at timestamptz not null default now(),
  file_name text not null default '',
  validation_status text not null default 'unknown',
  errors_count integer not null default 0,
  warnings_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.buk_template_compare_logs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  compared_by uuid references public.profiles(id) on delete set null,
  compared_at timestamptz not null default now(),
  date_from date not null,
  date_to date not null,
  sheet_name text not null default 'Reporte carga BUK',
  reference_file_name text not null default '',
  reference_file_sha256 text not null default '',
  reference_file_size_bytes integer not null default 0,
  is_compatible boolean not null default false,
  errors_count integer not null default 0,
  warnings_count integer not null default 0,
  result_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.import_batches (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  source_type text not null,
  file_name text not null,
  status public.import_batch_status not null default 'preview',
  created_by uuid references public.profiles(id) on delete set null,
  summary jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.import_preview_rows (
  id uuid primary key default gen_random_uuid(),
  batch_id uuid not null references public.import_batches(id) on delete cascade,
  sheet_name text not null,
  row_number integer not null,
  action text not null,
  status text not null default 'ok',
  message text not null default '',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (batch_id, sheet_name, row_number)
);

create table if not exists public.month_closures (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid not null references public.properties(id) on delete cascade,
  year integer not null,
  month integer not null check (month between 1 and 12),
  status public.month_closure_status not null default 'open',
  closed_by uuid references public.profiles(id) on delete set null,
  closed_at timestamptz,
  reopened_by uuid references public.profiles(id) on delete set null,
  reopened_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, property_id, year, month)
);

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  property_id uuid references public.properties(id) on delete set null,
  user_id uuid references public.profiles(id) on delete set null,
  action text not null,
  entity_type text not null,
  entity_id text not null default '',
  before jsonb not null default '{}'::jsonb,
  after jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- =========================
-- UPDATED_AT TRIGGER
-- =========================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'tenants', 'properties', 'profiles', 'role_profiles', 'user_tenant_roles',
    'module_activations', 'areas', 'user_property_permissions',
    'user_area_permissions', 'workers', 'shifts', 'special_states',
    'schedule_assignments', 'schedule_pattern_templates',
    'schedule_range_templates', 'buk_export_configs', 'buk_export_logs',
    'buk_template_compare_logs', 'import_batches', 'import_preview_rows',
    'month_closures', 'audit_logs'
  ]
  loop
    execute format('drop trigger if exists %I_set_updated_at on public.%I', table_name, table_name);
    execute format(
      'create trigger %I_set_updated_at before update on public.%I for each row execute function public.set_updated_at()',
      table_name,
      table_name
    );
  end loop;
end $$;

-- =========================
-- ACCESS HELPER FUNCTIONS
-- =========================

create or replace function public.current_user_is_super_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.profiles p
    where p.id = auth.uid()
      and p.is_active = true
      and p.is_super_admin = true
  );
$$;

create or replace function public.current_user_has_tenant_access(target_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.current_user_is_super_admin()
    or exists (
      select 1
      from public.user_tenant_roles utr
      join public.profiles p on p.id = utr.user_id
      where utr.user_id = auth.uid()
        and utr.tenant_id = target_tenant_id
        and p.is_active = true
    );
$$;

create or replace function public.current_user_has_tenant_role(target_tenant_id uuid, allowed_roles public.app_role[])
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.current_user_is_super_admin()
    or exists (
      select 1
      from public.user_tenant_roles utr
      join public.profiles p on p.id = utr.user_id
      where utr.user_id = auth.uid()
        and utr.tenant_id = target_tenant_id
        and utr.role = any(allowed_roles)
        and p.is_active = true
    );
$$;

create or replace function public.current_user_has_property_access(target_property_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.current_user_is_super_admin()
    or exists (
      select 1
      from public.user_property_permissions upp
      join public.profiles p on p.id = upp.user_id
      where upp.user_id = auth.uid()
        and upp.property_id = target_property_id
        and upp.can_access = true
        and p.is_active = true
    );
$$;

create or replace function public.current_user_can_property(target_property_id uuid, permission_key text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.current_user_is_super_admin()
    or exists (
      select 1
      from public.user_property_permissions upp
      join public.profiles p on p.id = upp.user_id
      where upp.user_id = auth.uid()
        and upp.property_id = target_property_id
        and upp.can_access = true
        and p.is_active = true
        and case permission_key
          when 'schedule' then upp.can_schedule
          when 'export_buk' then upp.can_export_buk
          when 'manage_workers' then upp.can_manage_workers
          when 'manage_shifts' then upp.can_manage_shifts
          when 'manage_areas' then upp.can_manage_areas
          when 'manage_users' then upp.can_manage_users
          when 'view_reports' then upp.can_view_reports
          when 'use_control' then upp.can_use_control
          else false
        end
    );
$$;

create or replace function public.current_user_has_area_access(target_area_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.current_user_is_super_admin()
    or exists (
      select 1
      from public.areas a
      where a.id = target_area_id
        and public.current_user_has_tenant_role(a.tenant_id, array['admin','operator']::public.app_role[])
        and public.current_user_has_property_access(a.property_id)
    )
    or exists (
      select 1
      from public.user_area_permissions uap
      join public.profiles p on p.id = uap.user_id
      where uap.user_id = auth.uid()
        and uap.area_id = target_area_id
        and uap.can_view = true
        and p.is_active = true
    );
$$;

create or replace function public.current_user_can_area_schedule(target_area_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select public.current_user_is_super_admin()
    or exists (
      select 1
      from public.areas a
      where a.id = target_area_id
        and public.current_user_has_tenant_role(a.tenant_id, array['admin','operator']::public.app_role[])
        and public.current_user_can_property(a.property_id, 'schedule')
    )
    or exists (
      select 1
      from public.user_area_permissions uap
      join public.profiles p on p.id = uap.user_id
      where uap.user_id = auth.uid()
        and uap.area_id = target_area_id
        and uap.can_schedule = true
        and p.is_active = true
    );
$$;

-- =========================
-- GRANTS FOR NETLIFY / SUPABASE CLIENT
-- =========================

grant usage on schema public to anon, authenticated, service_role;
grant execute on all functions in schema public to authenticated, service_role;

grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage, select on all sequences in schema public to authenticated;

-- No direct table grants to anon. Supabase Auth can still use the anon key
-- for sign-in/sign-up endpoints. App data requires an authenticated JWT.

-- =========================
-- ROW LEVEL SECURITY
-- =========================

alter table public.tenants enable row level security;
alter table public.properties enable row level security;
alter table public.profiles enable row level security;
alter table public.role_profiles enable row level security;
alter table public.user_tenant_roles enable row level security;
alter table public.module_activations enable row level security;
alter table public.areas enable row level security;
alter table public.user_property_permissions enable row level security;
alter table public.user_area_permissions enable row level security;
alter table public.workers enable row level security;
alter table public.shifts enable row level security;
alter table public.special_states enable row level security;
alter table public.schedule_assignments enable row level security;
alter table public.schedule_pattern_templates enable row level security;
alter table public.schedule_range_templates enable row level security;
alter table public.buk_export_configs enable row level security;
alter table public.buk_export_logs enable row level security;
alter table public.buk_template_compare_logs enable row level security;
alter table public.import_batches enable row level security;
alter table public.import_preview_rows enable row level security;
alter table public.month_closures enable row level security;
alter table public.audit_logs enable row level security;

-- Tenants / properties
drop policy if exists tenants_select_allowed on public.tenants;
create policy tenants_select_allowed on public.tenants
for select to authenticated
using (public.current_user_has_tenant_access(id));

drop policy if exists tenants_super_admin_all on public.tenants;
create policy tenants_super_admin_all on public.tenants
for all to authenticated
using (public.current_user_is_super_admin())
with check (public.current_user_is_super_admin());

drop policy if exists properties_select_allowed on public.properties;
create policy properties_select_allowed on public.properties
for select to authenticated
using (public.current_user_has_property_access(id) or public.current_user_is_super_admin());

drop policy if exists properties_super_admin_all on public.properties;
create policy properties_super_admin_all on public.properties
for all to authenticated
using (public.current_user_is_super_admin())
with check (public.current_user_is_super_admin());

-- Profiles and user permissions
drop policy if exists profiles_select_allowed on public.profiles;
create policy profiles_select_allowed on public.profiles
for select to authenticated
using (
  id = auth.uid()
  or public.current_user_is_super_admin()
  or public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[])
);

drop policy if exists profiles_manage_allowed on public.profiles;
create policy profiles_manage_allowed on public.profiles
for update to authenticated
using (
  id = auth.uid()
  or public.current_user_is_super_admin()
  or public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[])
)
with check (
  id = auth.uid()
  or public.current_user_is_super_admin()
  or public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[])
);

drop policy if exists profiles_insert_self on public.profiles;
create policy profiles_insert_self on public.profiles
for insert to authenticated
with check (id = auth.uid() or public.current_user_is_super_admin());

drop policy if exists role_profiles_select_allowed on public.role_profiles;
create policy role_profiles_select_allowed on public.role_profiles
for select to authenticated
using (public.current_user_has_tenant_access(tenant_id));

drop policy if exists role_profiles_admin_all on public.role_profiles;
create policy role_profiles_admin_all on public.role_profiles
for all to authenticated
using (public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[]))
with check (public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[]));

drop policy if exists user_tenant_roles_select_allowed on public.user_tenant_roles;
create policy user_tenant_roles_select_allowed on public.user_tenant_roles
for select to authenticated
using (user_id = auth.uid() or public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[]));

drop policy if exists user_tenant_roles_admin_all on public.user_tenant_roles;
create policy user_tenant_roles_admin_all on public.user_tenant_roles
for all to authenticated
using (public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[]))
with check (public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[]));

drop policy if exists user_property_permissions_select_allowed on public.user_property_permissions;
create policy user_property_permissions_select_allowed on public.user_property_permissions
for select to authenticated
using (
  user_id = auth.uid()
  or public.current_user_can_property(property_id, 'manage_users')
  or public.current_user_is_super_admin()
);

drop policy if exists user_property_permissions_manage_allowed on public.user_property_permissions;
create policy user_property_permissions_manage_allowed on public.user_property_permissions
for all to authenticated
using (public.current_user_can_property(property_id, 'manage_users') or public.current_user_is_super_admin())
with check (public.current_user_can_property(property_id, 'manage_users') or public.current_user_is_super_admin());

drop policy if exists user_area_permissions_select_allowed on public.user_area_permissions;
create policy user_area_permissions_select_allowed on public.user_area_permissions
for select to authenticated
using (
  user_id = auth.uid()
  or public.current_user_can_property(property_id, 'manage_users')
  or public.current_user_is_super_admin()
);

drop policy if exists user_area_permissions_manage_allowed on public.user_area_permissions;
create policy user_area_permissions_manage_allowed on public.user_area_permissions
for all to authenticated
using (public.current_user_can_property(property_id, 'manage_users') or public.current_user_is_super_admin())
with check (public.current_user_can_property(property_id, 'manage_users') or public.current_user_is_super_admin());

-- Modules
drop policy if exists module_activations_select_allowed on public.module_activations;
create policy module_activations_select_allowed on public.module_activations
for select to authenticated
using (public.current_user_has_tenant_access(tenant_id));

drop policy if exists module_activations_super_admin_all on public.module_activations;
create policy module_activations_super_admin_all on public.module_activations
for all to authenticated
using (public.current_user_is_super_admin())
with check (public.current_user_is_super_admin());

-- Operational catalogs
drop policy if exists areas_select_allowed on public.areas;
create policy areas_select_allowed on public.areas
for select to authenticated
using (public.current_user_has_area_access(id));

drop policy if exists areas_manage_allowed on public.areas;
create policy areas_manage_allowed on public.areas
for all to authenticated
using (public.current_user_can_property(property_id, 'manage_areas'))
with check (public.current_user_can_property(property_id, 'manage_areas'));

drop policy if exists workers_select_allowed on public.workers;
create policy workers_select_allowed on public.workers
for select to authenticated
using (public.current_user_has_area_access(area_id));

drop policy if exists workers_manage_allowed on public.workers;
create policy workers_manage_allowed on public.workers
for all to authenticated
using (public.current_user_can_property(property_id, 'manage_workers'))
with check (public.current_user_can_property(property_id, 'manage_workers'));

drop policy if exists shifts_select_allowed on public.shifts;
create policy shifts_select_allowed on public.shifts
for select to authenticated
using (public.current_user_has_area_access(area_id));

drop policy if exists shifts_manage_allowed on public.shifts;
create policy shifts_manage_allowed on public.shifts
for all to authenticated
using (public.current_user_can_property(property_id, 'manage_shifts'))
with check (public.current_user_can_property(property_id, 'manage_shifts'));

drop policy if exists special_states_select_allowed on public.special_states;
create policy special_states_select_allowed on public.special_states
for select to authenticated
using (public.current_user_has_property_access(property_id));

drop policy if exists special_states_manage_allowed on public.special_states;
create policy special_states_manage_allowed on public.special_states
for all to authenticated
using (public.current_user_can_property(property_id, 'manage_shifts'))
with check (public.current_user_can_property(property_id, 'manage_shifts'));

-- Scheduling
drop policy if exists schedule_assignments_select_allowed on public.schedule_assignments;
create policy schedule_assignments_select_allowed on public.schedule_assignments
for select to authenticated
using (
  public.current_user_has_property_access(property_id)
  and exists (
    select 1
    from public.workers w
    where w.id = worker_id
      and public.current_user_has_area_access(w.area_id)
  )
);

drop policy if exists schedule_assignments_manage_allowed on public.schedule_assignments;
create policy schedule_assignments_manage_allowed on public.schedule_assignments
for all to authenticated
using (
  public.current_user_can_property(property_id, 'schedule')
  and exists (
    select 1
    from public.workers w
    where w.id = worker_id
      and public.current_user_can_area_schedule(w.area_id)
  )
)
with check (
  public.current_user_can_property(property_id, 'schedule')
  and exists (
    select 1
    from public.workers w
    where w.id = worker_id
      and public.current_user_can_area_schedule(w.area_id)
  )
);

drop policy if exists schedule_pattern_templates_select_allowed on public.schedule_pattern_templates;
create policy schedule_pattern_templates_select_allowed on public.schedule_pattern_templates
for select to authenticated
using (public.current_user_has_property_access(property_id));

drop policy if exists schedule_pattern_templates_manage_allowed on public.schedule_pattern_templates;
create policy schedule_pattern_templates_manage_allowed on public.schedule_pattern_templates
for all to authenticated
using (public.current_user_can_property(property_id, 'schedule'))
with check (public.current_user_can_property(property_id, 'schedule'));

drop policy if exists schedule_range_templates_select_allowed on public.schedule_range_templates;
create policy schedule_range_templates_select_allowed on public.schedule_range_templates
for select to authenticated
using (public.current_user_has_property_access(property_id));

drop policy if exists schedule_range_templates_manage_allowed on public.schedule_range_templates;
create policy schedule_range_templates_manage_allowed on public.schedule_range_templates
for all to authenticated
using (public.current_user_can_property(property_id, 'schedule'))
with check (public.current_user_can_property(property_id, 'schedule'));

-- BUK, imports, closures, audit
drop policy if exists buk_export_configs_select_allowed on public.buk_export_configs;
create policy buk_export_configs_select_allowed on public.buk_export_configs
for select to authenticated
using (public.current_user_can_property(property_id, 'export_buk') or public.current_user_can_property(property_id, 'view_reports'));

drop policy if exists buk_export_configs_admin_all on public.buk_export_configs;
create policy buk_export_configs_admin_all on public.buk_export_configs
for all to authenticated
using (public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[]))
with check (public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[]));

drop policy if exists buk_export_logs_select_allowed on public.buk_export_logs;
create policy buk_export_logs_select_allowed on public.buk_export_logs
for select to authenticated
using (public.current_user_can_property(property_id, 'export_buk') or public.current_user_can_property(property_id, 'view_reports'));

drop policy if exists buk_export_logs_insert_allowed on public.buk_export_logs;
create policy buk_export_logs_insert_allowed on public.buk_export_logs
for insert to authenticated
with check (public.current_user_can_property(property_id, 'export_buk'));

drop policy if exists buk_template_compare_logs_select_allowed on public.buk_template_compare_logs;
create policy buk_template_compare_logs_select_allowed on public.buk_template_compare_logs
for select to authenticated
using (public.current_user_can_property(property_id, 'export_buk') or public.current_user_can_property(property_id, 'view_reports'));

drop policy if exists buk_template_compare_logs_insert_allowed on public.buk_template_compare_logs;
create policy buk_template_compare_logs_insert_allowed on public.buk_template_compare_logs
for insert to authenticated
with check (public.current_user_can_property(property_id, 'export_buk'));

drop policy if exists import_batches_select_allowed on public.import_batches;
create policy import_batches_select_allowed on public.import_batches
for select to authenticated
using (
  public.current_user_can_property(property_id, 'manage_workers')
  or public.current_user_can_property(property_id, 'manage_shifts')
);

drop policy if exists import_batches_manage_allowed on public.import_batches;
create policy import_batches_manage_allowed on public.import_batches
for all to authenticated
using (
  public.current_user_can_property(property_id, 'manage_workers')
  or public.current_user_can_property(property_id, 'manage_shifts')
)
with check (
  public.current_user_can_property(property_id, 'manage_workers')
  or public.current_user_can_property(property_id, 'manage_shifts')
);

drop policy if exists import_preview_rows_select_allowed on public.import_preview_rows;
create policy import_preview_rows_select_allowed on public.import_preview_rows
for select to authenticated
using (
  exists (
    select 1
    from public.import_batches b
    where b.id = batch_id
      and (
        public.current_user_can_property(b.property_id, 'manage_workers')
        or public.current_user_can_property(b.property_id, 'manage_shifts')
      )
  )
);

drop policy if exists import_preview_rows_manage_allowed on public.import_preview_rows;
create policy import_preview_rows_manage_allowed on public.import_preview_rows
for all to authenticated
using (
  exists (
    select 1
    from public.import_batches b
    where b.id = batch_id
      and (
        public.current_user_can_property(b.property_id, 'manage_workers')
        or public.current_user_can_property(b.property_id, 'manage_shifts')
      )
  )
)
with check (
  exists (
    select 1
    from public.import_batches b
    where b.id = batch_id
      and (
        public.current_user_can_property(b.property_id, 'manage_workers')
        or public.current_user_can_property(b.property_id, 'manage_shifts')
      )
  )
);

drop policy if exists month_closures_select_allowed on public.month_closures;
create policy month_closures_select_allowed on public.month_closures
for select to authenticated
using (public.current_user_has_property_access(property_id));

drop policy if exists month_closures_admin_all on public.month_closures;
create policy month_closures_admin_all on public.month_closures
for all to authenticated
using (public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[]))
with check (public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[]));

drop policy if exists audit_logs_select_allowed on public.audit_logs;
create policy audit_logs_select_allowed on public.audit_logs
for select to authenticated
using (
  public.current_user_is_super_admin()
  or public.current_user_has_tenant_role(tenant_id, array['admin']::public.app_role[])
);

drop policy if exists audit_logs_insert_allowed on public.audit_logs;
create policy audit_logs_insert_allowed on public.audit_logs
for insert to authenticated
with check (public.current_user_has_tenant_access(tenant_id));

-- =========================
-- STORAGE BUCKETS FOR NETLIFY CLIENTS
-- =========================

insert into storage.buckets (id, name, public)
values
  ('pariwana-imports', 'pariwana-imports', false),
  ('pariwana-buk-exports', 'pariwana-buk-exports', false)
on conflict (id) do nothing;

drop policy if exists pariwana_imports_select_authenticated on storage.objects;
create policy pariwana_imports_select_authenticated on storage.objects
for select to authenticated
using (bucket_id = 'pariwana-imports');

drop policy if exists pariwana_imports_write_authenticated on storage.objects;
create policy pariwana_imports_write_authenticated on storage.objects
for insert to authenticated
with check (bucket_id = 'pariwana-imports');

drop policy if exists pariwana_buk_exports_select_authenticated on storage.objects;
create policy pariwana_buk_exports_select_authenticated on storage.objects
for select to authenticated
using (bucket_id = 'pariwana-buk-exports');

drop policy if exists pariwana_buk_exports_write_authenticated on storage.objects;
create policy pariwana_buk_exports_write_authenticated on storage.objects
for insert to authenticated
with check (bucket_id = 'pariwana-buk-exports');

-- =========================
-- SEED DATA
-- =========================

insert into public.tenants (name, slug, status)
values ('Pariwana Hostels', 'pariwana', 'active')
on conflict (slug) do update
set name = excluded.name,
    status = excluded.status,
    updated_at = now();

insert into public.properties (tenant_id, name, slug, location, status)
select t.id, 'Pariwana Lima', 'lima', 'Lima', 'active'
from public.tenants t
where t.slug = 'pariwana'
on conflict (tenant_id, slug) do update
set name = excluded.name,
    location = excluded.location,
    status = excluded.status,
    updated_at = now();

insert into public.properties (tenant_id, name, slug, location, status)
select t.id, 'Pariwana Cusco', 'cusco', 'Cusco', 'active'
from public.tenants t
where t.slug = 'pariwana'
on conflict (tenant_id, slug) do update
set name = excluded.name,
    location = excluded.location,
    status = excluded.status,
    updated_at = now();

insert into public.module_activations (tenant_id, module_key, is_enabled, enabled_at)
select t.id, module_key, true, now()
from public.tenants t
cross join (
  values
    ('workers'),
    ('areas'),
    ('shifts'),
    ('special_states'),
    ('schedule_assignments'),
    ('next_15_days_control'),
    ('buk_report'),
    ('buk_preview'),
    ('buk_validator'),
    ('users_permissions'),
    ('import_export'),
    ('audit'),
    ('buk_config'),
    ('month_close'),
    ('team_schedule_pdf')
) as modules(module_key)
where t.slug = 'pariwana'
on conflict (tenant_id, module_key) do update
set is_enabled = excluded.is_enabled,
    updated_at = now();

insert into public.role_profiles (tenant_id, code, name, base_role, description, permissions, is_system, active)
select
  t.id,
  role_data.code,
  role_data.name,
  role_data.base_role::public.app_role,
  role_data.description,
  role_data.permissions::jsonb,
  true,
  true
from public.tenants t
cross join (
  values
    (
      'super-administrador',
      'Super Administrador',
      'super_admin',
      'Acceso total a todos los tenants, sedes y funciones.',
      '{"all": true}'
    ),
    (
      'administrador',
      'Administrador',
      'admin',
      'Acceso completo dentro de la sede asignada.',
      '{"schedule": true, "export_buk": true, "manage_workers": true, "manage_shifts": true, "manage_areas": true, "manage_users": true, "view_reports": true, "use_control": true}'
    ),
    (
      'operador',
      'Operador',
      'operator',
      'Gestiona trabajadores, turnos, asignaciones, control y reportes permitidos.',
      '{"schedule": true, "export_buk": true, "manage_workers": true, "manage_shifts": true, "manage_areas": false, "manage_users": false, "view_reports": true, "use_control": true}'
    ),
    (
      'supervisor',
      'Supervisor',
      'supervisor',
      'Ve y asigna horarios solo en sus areas autorizadas.',
      '{"schedule": true, "export_buk": false, "manage_workers": false, "manage_shifts": false, "manage_areas": false, "manage_users": false, "view_reports": true, "use_control": false}'
    )
) as role_data(code, name, base_role, description, permissions)
where t.slug = 'pariwana'
on conflict (tenant_id, code) do update
set name = excluded.name,
    base_role = excluded.base_role,
    description = excluded.description,
    permissions = excluded.permissions,
    is_system = excluded.is_system,
    active = excluded.active,
    updated_at = now();

insert into public.buk_export_configs (
  tenant_id,
  property_id,
  sheet_name,
  date_format,
  include_area,
  include_worker_name,
  document_column_name,
  name_column_name,
  area_column_name,
  header_row,
  first_data_row,
  export_format
)
select
  p.tenant_id,
  p.id,
  'Reporte carga BUK',
  '%d-%m-%Y',
  true,
  true,
  'RUT',
  'Nombre',
  'Area',
  2,
  3,
  'xlsx'
from public.properties p
join public.tenants t on t.id = p.tenant_id
where t.slug = 'pariwana'
on conflict (tenant_id, property_id) do update
set sheet_name = excluded.sheet_name,
    date_format = excluded.date_format,
    include_area = excluded.include_area,
    include_worker_name = excluded.include_worker_name,
    document_column_name = excluded.document_column_name,
    name_column_name = excluded.name_column_name,
    area_column_name = excluded.area_column_name,
    header_row = excluded.header_row,
    first_data_row = excluded.first_data_row,
    export_format = excluded.export_format,
    updated_at = now();

-- Useful indexes for operational screens.
create index if not exists idx_properties_tenant_status on public.properties(tenant_id, status);
create index if not exists idx_areas_property_active on public.areas(property_id, active);
create index if not exists idx_workers_property_area_active on public.workers(property_id, area_id, active);
create index if not exists idx_shifts_property_area_active on public.shifts(property_id, area_id, active);
create index if not exists idx_assignments_property_date on public.schedule_assignments(property_id, work_date);
create index if not exists idx_assignments_worker_date on public.schedule_assignments(worker_id, work_date);
create index if not exists idx_import_batches_property_created on public.import_batches(property_id, created_at desc);
create index if not exists idx_audit_logs_tenant_created on public.audit_logs(tenant_id, created_at desc);

commit;
