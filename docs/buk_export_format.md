# Formato BUK (referencia oficial)

Fuente: pestaña `Reporte carga BUK` del archivo `PRUEBA HORARIOS GENERALES 2026.xlsx`.

## Estructura
- Fila 1:
  - `A1`: `Trabajadores`
  - `D1..`: mes en formato `MM-YYYY`
- Fila 2:
  - `A2`: `RUT`
  - `B2`: `Nombre`
  - `C2`: `Área`
  - `D2..`: fechas en `DD-MM-YYYY`
- Fila 3 en adelante:
  - Documento
  - Nombre completo
  - Área
  - Código BUK por fecha

## Reglas
- Estados especiales confirmados (`OFF`, `VACACIONES`, `LICENCIA`) exportan `D`.
- Códigos de turno son válidos para BUK y los define el usuario.
- El exportador debe priorizar exactitud de datos sobre estilo visual.
