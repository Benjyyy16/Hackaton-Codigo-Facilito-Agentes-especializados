---
name: api-security-review
description: Se activa cuando se añade o modifica una ruta HTTP, middleware, dependencia de autenticación o manejo de errores expuesto al cliente.
---

# api-security-review

## Responsabilidad

Verificar que las rutas HTTP no filtran información interna, validan entradas correctamente y respetan las políticas de seguridad.

## Cuándo activar

- Se crea o modifica una ruta en `api/routes/`.
- Se cambia un middleware o dependencia de auth.
- Se ajusta el manejo de excepciones (`core/exceptions.py`).
- Se expone un nuevo endpoint público.
- Se modifica CORS.

## Procedimiento

1. Verificar que la ruta no construye `HTTPException` directo — debe elevar errores de dominio.
2. Confirmar que el cuerpo de error es uniforme y no filtra internals.
3. Verificar que inputs pasan por Pydantic (no raw dicts del request body).
4. Comprobar que webhooks validan firma/secreto ANTES de procesar.
5. Verificar que `request_id` se propaga y devuelve en respuesta.
6. Confirmar que no hay `print()` ni `logging.debug(payload)` con datos sensibles.
7. Verificar CORS: producción no usa `*`.
8. Comprobar que rutas demo están protegidas por flag de entorno.
9. Verificar que la ruta no expone `service_role_key` ni secretos en respuestas.

## Salida esperada

- Lista de issues de seguridad encontrados con severidad.
- Confirmación de que errores son opacos.
- Verificación de CORS y validación de inputs.

## Límites

- NO implementa auth de usuario (fuera de scope del MVP).
- NO audita el código de los agentes (eso es architecture-audit).
- NO prueba penetración — solo revisión estática de código.
