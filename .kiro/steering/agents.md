---
inclusion: auto
---

# Contrato de Agentes

## Protocolo común

Todo agente implementa el mismo contrato:

```python
class Agent(Protocol):
    name: str
    def run(self, context: AgentContext) -> AgentOutput: ...
```

- Entrada: `CommitmentSnapshot` (congelado, `frozen=True`) + contexto del proyecto + eventos recientes.
- Salida: `AgentOutput` con findings, evidencia, score, acciones recomendadas, información faltante.
- Sin `async`, sin I/O, sin dependencias de framework. Función pura de datos a datos.

## Reglas que un agente DEBE cumplir

1. Respaldar cada hallazgo con al menos una `Evidence`. Sin evidencia, el hallazgo pesa menos en la correlación.
2. Declarar `confidence` honestamente: dato duro → cerca de 1.0; inferencia LLM → más bajo.
3. Declarar `missing_information` cuando no puede concluir, en lugar de rellenar con suposiciones.
4. Si propone una acción, `requires_human_approval=True` salvo para acciones informativas.

## Lo que un agente NO puede hacer

| Prohibición | Razón |
|---|---|
| Inventar evidencia o datos | Un hallazgo sin fuente verificable destruye la confianza del sistema |
| Declarar integraciones probadas sin haberlas ejecutado | Falso positivo de salud es peor que no reportar |
| Importar `fastapi`, `supabase`, `httpx` | Rompería la pureza y la testabilidad sin red |
| Escribir directamente en BD (bypass de repositorios) | El repositorio es la única puerta; sin él no hay auditoría |
| Ejecutar acciones críticas sin aprobación | El sistema propone, el humano decide. `DecisionRepository` lo garantiza |
| Mutar el `CommitmentSnapshot` que recibe | Es `frozen=True` por diseño; un agente no altera el contexto de otro |
| Hacer llamadas de red | El provider trae los datos ANTES; el agente solo razona sobre ellos |

## Orquestador

El `OrchestratorAgent` ejecuta los agentes especializados, cada uno en su propio `try/except`:
- Si uno falla → se registra, se marca `is_partial=True`, el análisis sigue.
- Agrega con pesos declarados como constantes con nombre.
- Produce `RiskCase` con cadena causal, pre-mortem y tres escenarios obligatorios.
