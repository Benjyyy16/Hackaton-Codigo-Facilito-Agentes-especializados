---
name: orchestrator-analysis
description: Se activa cuando se trabaja con el orquestador de agentes, la correlación de hallazgos, generación de RiskCase o el flujo completo de análisis.
---

# orchestrator-analysis

## Responsabilidad

Garantizar que el orquestador correlaciona correctamente los outputs de los agentes especializados en un RiskCase coherente.

## Cuándo activar

- Se modifica `agents/orchestrator.py` o `services/orchestrator_service.py`.
- Se ajustan los pesos de combinación de riesgo.
- Se trabaja en la cadena causal, pre-mortem o escenarios.
- Se cambia la lógica de tolerancia a fallos parciales.

## Procedimiento

1. Verificar que cada agente se ejecuta en su propio `try/except` — fallo individual no tumba el flujo.
2. Confirmar que `is_partial=True` se marca cuando un agente falla.
3. Verificar la combinación de scores: pesos como constantes con nombre, no números mágicos.
4. Confirmar que la cadena causal (`CausalStep`) conecta causas con efectos entre agentes.
5. Verificar pre-mortem: asume el fallo consumado, trabaja hacia atrás.
6. Confirmar los 3 escenarios obligatorios: `do_nothing`, `add_capacity`, `renegotiate_scope`.
7. Verificar separación explícita: `facts` vs `inferences` vs `assumptions`.
8. Confirmar que `missing_information` se propaga desde los agentes.
9. Verificar que el score consolidado determina la severidad por tramos (40/60/80).

## Salida esperada

- `RiskCase` completo con todos los campos obligatorios.
- Confirmación de tolerancia a fallos parciales.
- Verificación de que la alerta se dispara solo cuando `score >= RISK_ALERT_THRESHOLD`.

## Límites

- NO decide los pesos — eso es calibración de producto.
- NO sustituye la lógica de los agentes individuales.
- NO persiste directamente — el servicio de orquestación se encarga.
