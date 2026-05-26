# Mapeo Excel -> Base de datos

## Datos
- `Datos!C2` -> `Property.name`
- `Datos!C6:C18` -> `Area.name`
- `Datos!H6:H9` -> `SpecialState.name`
- `Datos!H18:I18` -> rango de fechas para preview/export BUK

## Trabajadores
Hoja `Reg. de trabajadores x area`:
- `A` DNI -> `Worker.document_number`
- `B` Nombres -> `Worker.first_name`
- `C` Apellidos -> `Worker.last_name`
- `D` Área -> `Worker.area`

## Turnos
Hoja `Reg. Horarios x área`:
- `A` nombre -> `Shift.name`
- `B` código BUK -> `Shift.buk_code`
- `C` área -> `Shift.area`
- `D` horario -> `Shift.start_time/end_time`
- `E` refrigerio -> `Shift.break_start/break_end`

## Asignaciones
Hojas mensuales 2026:
- Fila tipo `TURNO` -> `ScheduleAssignment.shift`
- Estado especial -> `ScheduleAssignment.special_state`
