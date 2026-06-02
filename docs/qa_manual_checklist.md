# QA manual (Fase 4)

Este checklist valida el flujo operativo principal en UI para `Admin`, `Operador` y `Supervisor`.

## Precondiciones
- Servidor local levantado en `http://127.0.0.1:8000`.
- Tenant inicial: `Pariwana Hostels`.
- Sedes: `Pariwana Cusco` y `Pariwana Lima`.
- Modulos activos para el tenant.
- Datos minimos cargados: areas, trabajadores, turnos, estados especiales, asignaciones de ejemplo.

## 1) Login y contexto
1. Iniciar sesion con cada rol (`Admin`, `Operador`, `Supervisor`).
2. Seleccionar tenant/sede desde el header.
3. Verificar que el menu lateral respete el rol y modulos activos.

Criterio esperado:
- El usuario solo ve sedes autorizadas.
- Modulos desactivados no aparecen o muestran error de modulo desactivado.

## 2) Asignacion mensual
1. Ir a `Asignacion`.
2. Filtrar por mes, area y trabajador.
3. Asignar turno/estado por celda.
4. Probar acciones masivas:
   - Estado por dia
   - Turno por dia
   - Rango de estado
   - Copia de semana/mes
5. Verificar continuidad de contexto (`worker_q`, `focus_date`) despues de guardar.

Criterio esperado:
- No hay errores 500.
- Supervisor/Operador con restriccion de area no puede operar fuera de su area.
- Si el mes esta cerrado, la grilla queda en solo lectura.

## 3) Control 15 dias
1. Ingresar a `Control 15 dias` con `Admin`/`Operador`.
2. Ver pendientes por trabajador/fecha.
3. Usar enlace de correccion a Asignacion.

Criterio esperado:
- Solo `Admin` y `Operador` acceden al modulo.
- El enlace abre Asignacion en el mes/area/trabajador correctos con `focus_date`.
- Si el operador tiene areas restringidas, solo ve pendientes de esas areas.

## 4) Importaciones
1. Ir a `Importaciones`.
2. Cargar archivo de trabajadores (CSV/XLSX) y revisar preview.
3. Cargar archivo de turnos por area (CSV/XLSX) y revisar preview.
4. Confirmar importacion.

Criterio esperado:
- Vista previa muestra detectados/nuevos/actualizados/errores.
- No aparece contenido tecnico crudo en la UI.
- Se respetan permisos por modulo y rol.

## 5) Reporte BUK (preview + validacion + export)
1. Ir a `Reporte BUK`.
2. Seleccionar rango de fechas.
3. Revisar validaciones (errores/advertencias).
4. Exportar CSV y XLSX.
5. Probar `exportar con observaciones`:
   - `Operador`: debe bloquear si hay errores.
   - `Admin`: puede exportar con observaciones.

Criterio esperado:
- Preview muestra solo trabajadores/areas autorizadas del usuario.
- Si hay errores bloqueantes, no exporta salvo override admin.
- Logs de exportacion se registran.

## 6) Cierre de mes
1. Ir a `Cierre de mes`.
2. Cerrar periodo con `Admin`.
3. Intentar editar Asignacion en periodo cerrado.
4. Reabrir periodo.

Criterio esperado:
- Solo `Admin` puede cerrar/reabrir.
- En periodo cerrado no se permiten cambios.
- La pantalla muestra si el reporte BUK del periodo fue generado.

## 7) Auditoria
1. Ejecutar acciones de alta/edicion/asignacion/importacion/exportacion/cierre.
2. Revisar `Auditoria`.

Criterio esperado:
- Se registran accion, entidad, usuario, tenant, sede y payload antes/despues cuando aplica.

## 8) Permisos de seguridad (regresion)
1. Supervisor intenta crear trabajador/turno.
2. Operador restringido intenta asignar fuera de su area.
3. Usuario sin permiso intenta exportar BUK.

Criterio esperado:
- Respuesta denegada (`403`) o mensaje de contexto de permiso.
- No se crean/modifican datos indebidamente.
