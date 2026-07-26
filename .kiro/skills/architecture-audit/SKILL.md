---
name: architecture-audit
description: Se activa cuando se modifica la estructura de módulos, se añade una dependencia entre capas o se propone una nueva integración.
---

# architecture-audit

## Responsabilidad

Verificar que el código respeta la regla de dependencia hacia dentro y los contratos entre capas.

## Cuándo activar

- Se agrega un import entre capas.
- Se crea un módulo nuevo.
- Se propone mover lógica de una capa a otra.
- Se añade un provider o integración.

## Procedimiento

1. Leer el import graph del módulo afectado.
2. Verificar que no hay dependencia invertida (ruta → repo directo, agente → httpx, etc.).
3. Confirmar que los agentes no importan nada fuera de `schemas/` y `agents/`.
4. Verificar que los providers implementan el protocolo de `providers/base.py`.
5. Comprobar que los servicios no tocan `client.table(...)`.
6. Si hay violación, señalar la línea exacta y proponer la corrección.

## Salida esperada

- Lista de violaciones encontradas (archivo, línea, regla rota).
- Propuesta de corrección para cada una.
- Confirmación de que el grafo de dependencias es acíclico dentro de la capa.

## Límites

- NO modifica código sin aprobación.
- NO evalúa calidad del código (eso es code review), solo estructura.
- NO propone reorganizaciones "por estética" — solo si hay violación de regla.
