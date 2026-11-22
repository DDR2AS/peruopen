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

## Estado por dataset (verificado el 2026-11-21)

| Dataset | Estado | Licencia / términos | Atribución | Redistribución | Evidencia |
|---|---|---|---|---|---|
| `macro` (BCRP) | `open-attribution` | Condiciones de uso de BCRPData: "puede reproducirse total o parcialmente, sin autorización expresa, siempre y cuando se cite la fuente" | Sí | Sí | https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/condiciones-de-uso |
| `macro` (UIT) | `open-attribution` | Dato normativo (D.S. del MEF), publicado por SUNAT | Sí (se cita el D.S.) | Sí | https://www.sunat.gob.pe/indicestasas/uit.html |
| `geo` (INEI) | `open-attribution` | ODC-BY (licencia del dataset en datosabiertos.gob.pe) | Sí | Sí | http://opendefinition.org/licenses/odc-by/ |
| `calendario` | `open-attribution` | Normas legales públicas (leyes y D.S.) | Sí (se cita la norma) | Sí | https://www.gob.pe/feriados |
| `sunat` (padrón RUC) | `public-review-terms` | Sin licencia explícita. SUNAT lo publica para descarga libre. Incluye **datos personales** de personas naturales (Ley 29733) | Sí | ⚠️ Decisión pendiente | https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html |
