# `sunat_uit`: Unidad Impositiva Tributaria

**Fuente:** tabla oficial de SUNAT (`https://www.sunat.gob.pe/indicestasas/uit.html`).
Cada valor lo fija un Decreto Supremo del MEF.
**Licencia:** dato normativo público. Se cita el D.S. correspondiente.
**Actualización:** anual (el D.S. sale en diciembre para el año siguiente).
**Cobertura:** 1994 en adelante.

Clave primaria: `year`.

| Columna | Tipo | Descripción |
|---|---|---|
| `year` | int16 | Año de vigencia |
| `value` | int32 | Valor en soles (S/) |
| `legal_basis` | string | Decreto Supremo, p. ej. `D.S. N° 301-2025-EF` |

## Decisiones

- **Empieza en 1994.** En 1993 hubo valores por semestre fijados por R.M., y en
  1992 regía la URT, no la UIT.
- **1996 tuvo dos valores** (cambió en febrero). Se usa S/ 2,200 (D.S. N°
  012-96-EF), que estuvo vigente casi todo el año.

## Validaciones antes de publicar

- Años consecutivos, sin huecos.
- Está el año en curso.
- El valor nunca baja de un año al siguiente.
- Valores entre S/ 1,000 y S/ 100,000.

## Ejemplos

```python
import peruopen as pe

pe.macro.uit()  # año actual -> 5500
pe.macro.uit(2020)  # -> 4300
pe.macro.uit_history().df()
```
