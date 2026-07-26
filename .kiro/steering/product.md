---
inclusion: auto
---

# Datgent — Producto

## Qué es

Sistema multiagente que detecta compromisos empresariales en riesgo correlacionando señales de Finanzas, Jira, GitHub y Supabase. No son cuatro dashboards: es UN análisis integrado del MISMO compromiso.

## Problema que resuelve

Las organizaciones incumplen compromisos porque las señales de alerta viven en silos (tablero de Jira, repositorio, ERP, base de datos). Cuando alguien conecta los puntos, ya es tarde. Datgent los conecta automáticamente, calcula riesgo consolidado y propone acciones — pero nunca las ejecuta sin aprobación humana.

## Entidad central: Commitment

Todo gira alrededor del Commitment. No hay entidad "alerta" que exista sola ni "hallazgo" sin compromiso asociado. Los agentes reciben un `CommitmentSnapshot` congelado y devuelven un `AgentOutput` referido al mismo compromiso. El orquestador los correlaciona en un `RiskCase`.

Cadena causal: hallazgo de código + hallazgo financiero + hallazgo de timeline → explicación de POR QUÉ el compromiso está en riesgo, no solo QUE lo está.

## A quién sirve

- **Directores de proyecto**: visibilidad temprana de incumplimientos.
- **CTOs / VP Engineering**: correlación técnica-financiera para decisiones de capacidad.
- **Equipos de cumplimiento**: trazabilidad de cada decisión con evidencia auditable.
- **Producto / PMO**: priorización basada en exposición económica real, no en intuición.

## Principios de diseño

1. El sistema **propone**, nunca ejecuta acciones críticas sin aprobación.
2. Sin evidencia un hallazgo es opinión — los agentes están obligados a respaldar.
3. Separación explícita entre hechos, inferencias y suposiciones.
4. Un agente que falla no tumba el análisis: se marca parcial y se entrega lo que se tiene.
5. Los secretos nunca aparecen en respuestas, logs ni configuraciones persistidas.
