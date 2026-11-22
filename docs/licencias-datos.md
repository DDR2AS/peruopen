# Licencias de los datos

El código de peruopen es MIT, pero **cada dataset conserva la licencia de su
fuente oficial**. Cada uno registra su `reuse_policy` en el catálogo:

| Campo | Significado |
|---|---|
| `status` | `open-attribution` (abierto con atribución) · `public-review-terms` (público, con términos por revisar) · `restricted` (no se redistribuye) |
| `license` | Nombre de la licencia (p. ej. ODC-BY, CC BY 4.0) |
| `license_url` | Link al texto o a los términos |
| `attribution_required` | Si hay que citar la fuente |
| `redistribution_ok` | Si se puede redistribuir el dato. Si es `false`, se publica **solo** la metadata y el link |

## Estado por dataset

| Dataset | Estado | Licencia / términos | Atribución | Redistribución | Evidencia |
|---|---|---|---|---|---|
| `macro_series` (BCRP) | `open-attribution` | Condiciones de uso de BCRPData: "puede reproducirse total o parcialmente, sin autorización expresa, siempre y cuando se cite la fuente" | Sí | Sí | https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/condiciones-de-uso |
| `macro_uit` (SUNAT) | `open-attribution` | Dato normativo (D.S. del MEF), publicado por SUNAT | Sí (se cita el D.S.) | Sí | https://www.sunat.gob.pe/indicestasas/uit.html |
