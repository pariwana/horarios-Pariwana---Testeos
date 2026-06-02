# Formato BUK (referencia oficial)

Fuente: hoja `Reporte carga BUK` del archivo `PRUEBA HORARIOS GENERALES 2026.xlsx`.

## Estructura base (version actual)
- Fila de mes: por defecto fila `1` (configurable).
- Fila de encabezados: por defecto fila `2` (configurable).
- Fila inicial de datos: por defecto fila `3` (configurable).

Columnas fijas (configurables):
- Documento (`RUT` por defecto)
- Nombre (`Nombre` por defecto, opcional)
- Área (`Área` por defecto, opcional)

Columnas por fecha:
- Una columna por dia del rango seleccionado.
- Formato de fecha configurable (`%d-%m-%Y` por defecto).

## Reglas de codigos
- Si hay turno asignado: se exporta `shift.buk_code`.
- Si hay estado especial asignado: se exporta `special_state.buk_code`.
- Si no hay asignacion: celda vacia.

## Reglas operativas
- El nombre de hoja se toma de `BukExportConfig.sheet_name`.
- El exportador respeta `header_row`, `first_data_row`, `date_format` y nombres de columnas del `BukExportConfig`.
- Antes de exportar se ejecuta el validador BUK.
- Si hay errores bloqueantes, solo un Administrador puede exportar con observaciones.

## Reglas de validacion implementadas (v1 actual)
- Trabajador activo sin documento: `error`.
- Trabajador activo sin horario en el rango: `warning`.
- Turno activo sin codigo BUK: `error`.
- Estado especial usado sin codigo BUK: `error`.
- Codigo BUK duplicado entre turnos/estados especiales: `error`.
- Asignacion fuera de vigencia del trabajador (antes de inicio / despues de cese): `error`.
- Bandera nocturna inconsistente en turno (`is_night_shift`): `warning`.
- Asignaciones duplicadas para trabajador y fecha: `error`.

## Comparador de compatibilidad de plantilla
Se implemento un comparador estructural en `BukExportService.compare_template_compatibility(...)` para evaluar archivo generado vs referencia.

Valida:
- existencia de hoja `Reporte carga BUK`;
- fila de encabezado con fechas;
- columna inicial de fechas;
- etiquetas de columnas fijas (normalizadas);
- formato de fechas del encabezado (warning si difiere);
- fila inicial de datos (warning si difiere);
- `freeze_panes` (warning si difiere).

Evidencia:
- API: `POST /api/buk/compare-template/` con `download_report=true` devuelve un JSON descargable con el resultado.
- Web UI: en `Reporte BUK`, opcion `Comparar y descargar JSON`.
- Persistencia: cada comparacion se guarda en `BukTemplateCompareLog` con rango, usuario, referencia y resultado.
- Firma persistida: `reference_file_sha256` y `reference_file_size_bytes` para trazabilidad del archivo base usado.
- Reuso operativo: en la UI se muestra una URL API lista para copiar con los filtros actuales del historial.

## Comando CLI de validacion estructural
Se agrego el comando:

```bash
python manage.py check_buk_template_compatibility \
  --tenant-slug pariwana-hostels \
  --property-slug pariwana-cusco \
  --date-from 2026-05-28 \
  --date-to 2026-06-11 \
  --reference-file "D:/Descargas/PRUEBA HORARIOS GENERALES 2026.xlsx" \
  --sheet-name "Reporte carga BUK" \
  --output-json "docs/buk_compare_latest.json"
```

Comportamiento:
- Retorna error si hay incompatibilidades (`errors`).
- Con `--strict-warnings` tambien falla si hay `warnings`.
- Emite JSON con `reference` y `candidate` para auditoria tecnica.
