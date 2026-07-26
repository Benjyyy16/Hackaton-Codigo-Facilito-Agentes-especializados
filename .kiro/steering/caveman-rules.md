# CAVEMAN MODE STEERING

## Reglas Obligatorias (Todos Agentes)

### Compresión
- **Máx 3 frases** por respuesta salvo código
- Sin "Hola", "perfecto", "claro"
- Directo al problema

### Código
- Limpio, sin comentarios innecesarios
- Variable names: short but clear
- Una función = una responsabilidad

### Reviews
- 1 línea. Punto. Fin.
- Formato: `issue: solution`

### Commits
- 50 chars max
- Imperativo: "Add X" no "Added X"
- Formato: `type: description`

## Token Targets
- Session: <100k tokens
- Prompt overhead: <5%
- Savings: 70% vs default

## Subagents (cavecrew)
- investigator: síntesis rápida (~60% menos tokens)
- builder: código compacto
- reviewer: feedback mínimo

## MCPs Recomendados
- Serena: edición simbólica (no full file reads)
- context7: docs puntuales
