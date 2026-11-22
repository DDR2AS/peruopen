# 2. Conectar peruopen a Claude (MCP)

Con esto puedes preguntarle a Claude, en lenguaje normal, cosas como *"¿cuánto
subió el dólar este año?"*. Claude consulta los datos oficiales y te responde
citando la fuente.

## ¿Qué es un MCP?

**MCP** (*Model Context Protocol*) es la forma estándar de darle herramientas a
un asistente de IA. peruopen incluye un **servidor MCP**: un pequeño programa que
Claude Desktop arranca en tu computadora y que le ofrece cuatro herramientas:

| Herramienta | Qué hace |
|---|---|
| `list_datasets` | Le dice a Claude qué datos hay |
| `describe_dataset` | Le explica las columnas, la fuente oficial y la fecha del dato |
| `search_series` | Busca entre las ~17 000 series del BCRP la que corresponde a tu pregunta |
| `query` | Ejecuta una consulta SQL **de solo lectura** y devuelve el resultado |

Es seguro: el servidor solo acepta consultas `SELECT`, no puede leer otros
archivos de tu computadora, devuelve como máximo 1000 filas y corta cualquier
consulta que tarde más de 30 segundos.

```
Tú ──pregunta──▶ Claude Desktop ──usa las tools──▶ servidor peruopen (en tu PC)
                                                      │
                                         datos en caché ◀── Cloudflare (la primera vez)
```

## Opción A (recomendada): con `uv`

`uv` es un instalador de Python muy rápido. Con él, Claude Desktop descarga y
ejecuta peruopen solo, sin que instales nada más.

1. Instala `uv` siguiendo las instrucciones oficiales: https://docs.astral.sh/uv/getting-started/installation/
2. Abre la configuración de Claude Desktop (ver más abajo, **"Dónde está la configuración"**).
3. Agrega esto:

```json
{
  "mcpServers": {
    "peruopen": {
      "command": "uvx",
      "args": ["--from", "peruopen[mcp]", "peruopen-mcp"]
    }
  }
}
```

4. Reinicia Claude Desktop (ver **"Reiniciar de verdad"**).

## Opción B: con un entorno de Python propio (sin `uv`)

Así lo configuramos en la máquina de desarrollo. Funciona con el Python que ya tienes.

**1. Crear un entorno solo para el servidor e instalar peruopen con el extra `mcp`:**

Windows:

```bash
python -m venv %USERPROFILE%\.peruopen-mcp
%USERPROFILE%\.peruopen-mcp\Scripts\pip install "peruopen[mcp]"
```

Mac / Linux:

```bash
python3 -m venv ~/.peruopen-mcp
~/.peruopen-mcp/bin/pip install "peruopen[mcp]"
```

Esto crea el programa `peruopen-mcp` dentro de ese entorno.

**2. Comprobar que arranca** (opcional). Debería mostrar un recuadro de FastMCP y
quedarse esperando. Ciérralo con `Ctrl+C`:

```bash
%USERPROFILE%\.peruopen-mcp\Scripts\peruopen-mcp.exe
```

**3. Agregarlo a la configuración de Claude Desktop** con la **ruta completa**
al programa. En Windows las barras invertidas van dobles (`\\`) dentro del JSON:

```json
{
  "mcpServers": {
    "peruopen": {
      "command": "C:\\Users\\TU_USUARIO\\.peruopen-mcp\\Scripts\\peruopen-mcp.exe",
      "args": []
    }
  }
}
```

En Mac / Linux: `"command": "/Users/TU_USUARIO/.peruopen-mcp/bin/peruopen-mcp"`.

**4. Reiniciar Claude Desktop.**

Para actualizar peruopen más adelante:

```bash
%USERPROFILE%\.peruopen-mcp\Scripts\pip install -U "peruopen[mcp]"
```

## Dónde está la configuración

La forma más segura de encontrarla: en Claude Desktop, **Settings → Developer →
Edit Config**. Abre el archivo `claude_desktop_config.json` correcto.

Ubicaciones habituales:

| Sistema | Ruta |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Windows (instalado desde la Microsoft Store o con datos movidos) | Puede estar en `%LOCALAPPDATA%\Claude-Data\…\claude_desktop_config.json`. Usa **Edit Config** para no adivinar |
| Mac | `~/Library/Application Support/Claude/claude_desktop_config.json` |

⚠️ **Si el archivo ya tiene contenido**, no lo borres: agrega solo la parte de
`"mcpServers"`. Si ya existe `"mcpServers"`, agrega `"peruopen": {...}` dentro,
separado por una coma de los otros servidores. Antes de editar, guarda una copia.

Ejemplo de un archivo con otras configuraciones:

```json
{
  "preferences": { "...": "lo que ya tenías" },
  "mcpServers": {
    "peruopen": {
      "command": "uvx",
      "args": ["--from", "peruopen[mcp]", "peruopen-mcp"]
    }
  }
}
```

## Reiniciar de verdad

Cerrar la ventana no basta: Claude sigue abierto en segundo plano.

- **Windows:** clic derecho en el ícono de Claude de la bandeja del sistema (junto al reloj) → **Quit**.
- **Mac:** menú Claude → **Quit Claude** (o `Cmd+Q`).

Después ábrelo de nuevo.

## Probarlo

1. Abre un **chat nuevo**.
2. En el botón de herramientas (junto a la caja de texto) debería aparecer **peruopen**.
3. Pregunta, por ejemplo:

> ¿Cuánto ha variado el tipo de cambio del dólar en Perú este año? Dame el promedio por mes de 2026.

> ¿Cuál es la UIT de este año y cuánto ha subido desde 2015?

> Compara la inflación anual de Lima con la tasa de referencia del BCRP en los últimos 24 meses.

> ¿Cuántos dólares son 4 UIT al tipo de cambio más reciente?

> ¿Cómo ha evolucionado la morosidad de la banca en los últimos dos años?

La primera vez Claude te pedirá **permiso** para usar las herramientas de peruopen: acéptalo.

## Si no funciona

| Síntoma | Qué revisar |
|---|---|
| peruopen no aparece en las herramientas | ¿Reiniciaste con **Quit**? ¿El JSON es válido (comas, llaves, `\\`)? Pégalo en https://jsonlint.com para revisarlo |
| Aparece con error | **Settings → Developer**: muestra el estado del servidor y el error. Los logs están en la carpeta `logs` de Claude (archivos `mcp*.log`) |
| `uvx` no se reconoce | `uv` no está instalado o Claude no lo encuentra: usa la **Opción B**, o pon la ruta completa a `uvx` en `"command"` |
| `peruopen-mcp.exe` no existe | Instalaste `peruopen` sin el extra: `pip install "peruopen[mcp]"` (con comillas) |
| Claude dice que no puede ejecutar la consulta | Lee el mensaje: el servidor rechaza todo lo que no sea `SELECT` |

## Quitarlo

Borra el bloque `"peruopen"` de `"mcpServers"` en la configuración y reinicia
Claude Desktop. Si usaste la opción B, también puedes borrar la carpeta
`.peruopen-mcp`.

## También funciona en

- **Claude Code** (terminal):
  `claude mcp add peruopen -- uvx --from "peruopen[mcp]" peruopen-mcp`
- **Cursor, Windsurf y otros clientes MCP:** usan el mismo bloque JSON en su propia configuración de MCP.
