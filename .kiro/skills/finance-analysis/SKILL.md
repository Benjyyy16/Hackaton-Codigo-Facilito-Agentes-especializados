---
name: finance-analysis
description: Se activa cuando se trabaja con el agente financiero, cálculos de exposición económica, FIFO, asientos contables o decisiones con impacto monetario.
---

# finance-analysis

## Responsabilidad

Garantizar que el análisis financiero es correcto, transparente y NUNCA ejecuta acciones contables sin aprobación humana explícita.

## Cuándo activar

- Se modifica `agents/financial_agent.py` o `services/finance_service.py`.
- Se propone un cálculo de exposición financiera.
- Se trabaja con métodos de valorización (FIFO, LIFO, promedio ponderado).
- Se propone un asiento contable.
- Se calcula impacto económico de un compromiso.

## Procedimiento

### Antes de ejecutar FIFO o proponer asientos contables — VALIDAR/PREGUNTAR:

1. **Moneda funcional**: ¿en qué moneda opera la entidad? ¿Hay conversión?
2. **Política contable**: ¿NIIF, US GAAP, local? ¿Qué norma aplica?
3. **Periodo contable**: ¿a qué periodo se imputa? ¿Está cerrado?
4. **Método de valorización**: ¿FIFO, LIFO, promedio ponderado? ¿Está definido?
5. **Inventario inicial**: saldos de apertura verificados.
6. **Compras**: documentación de entradas al periodo.
7. **Consumos / ventas**: salidas del periodo con soporte.
8. **Devoluciones**: ajustes por devoluciones de compra o venta.
9. **Impuestos**: IVA, retenciones, impuestos específicos aplicables.
10. **Cuentas contables**: plan de cuentas y cuentas específicas a afectar.
11. **Regla de aprobación**: ¿quién aprueba? ¿Qué monto requiere doble aprobación?

### Flujo del agente

1. Calcular `financial_exposure` del compromiso: horas en riesgo × coste/hora + penalización.
2. Generar `Finding` con categoría `financial`, respaldado por `Evidence` (fuente: `finance`).
3. Si propone acción (`POST_ACCOUNTING_ENTRY`): `requires_human_approval = True` SIEMPRE.
4. Declarar `missing_information` si faltan datos contables.
5. Separar explícitamente: dato observado vs. estimación.

## Salida esperada

- `AgentOutput` con findings financieros, confidence basada en datos disponibles.
- Propuestas de asientos como `RecommendedAction` con `requires_human_approval=True`.
- Lista de información faltante cuando no se puede concluir.

## Límites

- **NUNCA publica asientos automáticamente**: solo propone, sujeto a aprobación humana vía `DecisionRepository`.
- NO asume política contable — la pregunta si no está configurada.
- NO ejecuta sin las 11 validaciones previas completas.
- NO inventa cifras cuando falta información — declara `missing_information`.
- NO accede a sistemas financieros directamente — recibe datos ya ingestados.
