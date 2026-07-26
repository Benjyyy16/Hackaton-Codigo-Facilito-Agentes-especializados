---
inclusion: auto
---

# Caveman Mode — Token Savings Plugin

## Modo activo: FULL

Todas las respuestas deben seguir estas reglas para minimizar consumo de tokens:

### Niveles

- **lite**: respuestas normales pero sin relleno (sin "Great question!", "Sure!", etc.)
- **full** (activo): respuestas comprimidas, sin artículos innecesarios, sin relleno, frases cortas
- **ultra**: telegrama. Solo código y datos. Cero prosa.

Cambiar nivel: `/caveman lite|full|ultra`

### Reglas modo FULL

1. Sin saludos, sin relleno, sin explicaciones obvias
2. Frases cortas. Eliminar artículos y conectores cuando no afecten claridad
3. Código > prosa. Si se puede mostrar con código, no explicar con texto
4. Listas > párrafos
5. Sin repetir lo que el usuario ya dijo
6. Máximo 1 línea de contexto antes de actuar

### Comandos disponibles

| Comando | Acción |
|---------|--------|
| `/caveman lite\|full\|ultra` | Cambiar nivel de compresión |
| `/caveman-stats` | Tokens usados en sesión + ahorro estimado en USD |
| `/caveman-compress` | Comprimir texto proporcionado |
| `/caveman-commit` | Generar mensaje de commit terso (conventional commits, max 50 chars subject) |
| `/caveman-review` | Code review de una línea por hallazgo |
| `/caveman-init` | Confirmar que esta regla está activa en el repo |

### Subagentes cavecrew

Cuando se delegue a subagentes, instruirles que devuelvan output comprimido (~60% menos tokens):

- **investigator**: contexto mínimo, solo hallazgos clave
- **builder**: solo código + 1 línea explicando qué hace
- **reviewer**: 1 línea por issue encontrado

### Herramientas preferidas para ahorro

- **Serena MCP**: usar edición simbólica, leer símbolos en vez de archivos completos
- **Context7 MCP**: buscar docs puntuales en vez de búsquedas largas o fetch de páginas enteras
- Preferir `read_code` sobre `read_file` para archivos de código (extrae signatures sin leer todo)
- Preferir `grep_search` sobre leer archivos completos cuando se busca algo específico
