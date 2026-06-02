# Fase 4 - Snapshot de aceptacion

- Ejecutado: 2026-05-29T15:21:10.494832+00:00
- Tenant: pariwana-hostels
- Sede: pariwana-cusco
- Rango evaluado: 2026-05-28 a 2026-06-11
- Referencia BUK: `D:\Descargas\PRUEBA HORARIOS GENERALES 2026.xlsx`
- Estado global: **PASS**

## Resultado checks
- qa_check_local: **PASS**
- check_buk_template_compatibility: **PASS**

## Evidencia
- JSON comparacion: `C:\Users\frazz\OneDrive\Documentos\App de RRHH Pariwana\docs\phase4_acceptance_snapshot_2026-05-29.json`

## Salida qa_check_local
```text
1/2 validate_demo_setup
2/2 smoke_test_webui
Local QA checks passed.
```

## Salida check_buk_template_compatibility
```text
{
  "tenant_slug": "pariwana-hostels",
  "property_slug": "pariwana-cusco",
  "date_from": "2026-05-28",
  "date_to": "2026-06-11",
  "sheet_name": "Reporte carga BUK",
  "is_compatible": true,
  "errors": [],
  "warnings": [],
  "reference": {
    "header_row": 2,
    "first_data_row": 3,
    "first_date_col": 4,
    "fixed_labels": [
      "RUT",
      "Nombre",
      "Área"
    ],
    "date_values": [
      "02-04-2026",
      "03-04-2026",
      "04-04-2026",
      "05-04-2026",
      "06-04-2026",
      "07-04-2026",
      "08-04-2026",
      "09-04-2026",
      "10-04-2026",
      "11-04-2026",
      "12-04-2026",
      "13-04-2026",
      "14-04-2026",
      "15-04-2026",
      "16-04-2026",
      "17-04-2026",
      "18-04-2026",
      "19-04-2026",
      "20-04-2026",
      "21-04-2026",
      "22-04-2026",
      "23-04-2026",
      "24-04-2026",
      "25-04-2026",
      "26-04-2026",
      "27-04-2026",
      "28-04-2026",
      "29-04-2026",
      "30-04-2026"
    ],
    "date_format": "%d-%m-%Y",
    "freeze_panes": "D3"
  },
  "candidate": {
    "header_row": 2,
    "first_data_row": 3,
    "first_date_col": 4,
    "fixed_labels": [
      "RUT",
      "Nombre",
      "Área"
    ],
    "date_values": [
      "28-05-2026",
      "29-05-2026",
      "30-05-2026",
      "31-05-2026",
      "01-06-2026",
      "02-06-2026",
      "03-06-2026",
      "04-06-2026",
      "05-06-2026",
      "06-06-2026",
      "07-06-2026",
      "08-06-2026",
      "09-06-2026",
      "10-06-2026",
      "11-06-2026"
    ],
    "date_format": "%d-%m-%Y",
    "freeze_panes": "D3"
  }
}
JSON guardado en: C:\Users\frazz\OneDrive\Documentos\App de RRHH Pariwana\docs\phase4_acceptance_snapshot_2026-05-29.json
Compatibilidad valida: errors=0, warnings=0.
```