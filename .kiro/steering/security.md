---
inclusion: auto
---

# Seguridad

## Secretos

- Toda credencial es `SecretStr` en `Settings`. Su `repr` la ofusca por defecto.
- Comparación segura: `hmac.compare_digest`. Nunca `==` para tokens ni secretos — evita side-channel por tiempo de respuesta.
- `config` de `provider_connections` almacena REFERENCIAS a secretos (`"secret_ref": "JIRA_API_TOKEN"`), nunca el valor.
- La service role key de Supabase NUNCA aparece en respuestas HTTP, logs ni payloads persistidos.

## Webhooks

### GitHub
- Firma HMAC SHA-256 en `X-Hub-Signature-256`. Se verifica con `hmac.compare_digest(expected, received)`.
- Sin firma válida → 401 inmediato, sin procesar el payload.

### Jira
- Jira Cloud no firma con HMAC. Se usa secreto compartido configurado en la URL o cabecera `X-Hook-Secret`.
- Comparación con `hmac.compare_digest`. Sin secreto válido → 401.

## CORS

- En desarrollo: `allow_origins=["*"]` (aceptable porque no hay datos reales).
- En producción: restringir a `FRONTEND_URL` configurado. El middleware ya existe, solo se ajusta la lista.

## Payloads

- Límite de tamaño: webhooks rechazan payloads > 1 MB antes de parsear.
- Validación Pydantic en toda entrada: campos desconocidos se ignoran (`extra="ignore"`).

## Timeouts

- `HTTP_TIMEOUT_SECONDS` configurable (default 10s, max 120s).
- Cada provider hereda el timeout. Un provider colgado no bloquea el servicio.

## Logs

- El filtro de `logging.py` redacta patrones de secreto conocidos (tokens, keys).
- Los errores de integración registran código de estado y ruta, NUNCA cabeceras ni tokens.
- `processing_error` en BD se trunca a 500 chars para no volcar trazas externas.

## Rutas demo

- Las rutas de demostración (`source: "demo"`) solo están disponibles cuando `ENV != production`.
- Datos de seed usan `CommitmentSource.DEMO` para identificarse y poder purgarse.

## SSRF

- URLs proporcionadas por usuarios (webhooks, source_url) se validan: solo esquemas `http`/`https`, no IPs privadas ni `localhost`.
- `httpx` no sigue redirects a hosts internos.

## Permisos mínimos

- RLS activo en TODAS las tablas. Sin políticas permisivas → la clave anónima no lee nada.
- El backend usa service role (bypasses RLS) porque opera como servicio de confianza.
- Si el frontend consulta directamente, se añaden políticas explícitas — hasta entonces la ausencia ES la política.

## Errores

- Cuerpo uniforme: `{"error": {"code": "...", "message": "...", "request_id": "..."}}`.
- NUNCA incluyen detalle interno: sin trazas de Python, sin valores de config, sin nombres de tabla.
- `ConfigurationError` nombra variables ausentes pero NUNCA sus valores.
