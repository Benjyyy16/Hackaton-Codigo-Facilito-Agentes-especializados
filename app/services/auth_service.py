"""Servicio de autenticación con JWT."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Final

import jwt

from app.core.config import Settings
from app.core.exceptions import DomainError
from app.schemas.auth import ACCESS_TOKEN_EXPIRE_MINUTES, CurrentUser, TokenResponse

JWT_ALGORITHM: Final[str] = "HS256"


class AuthenticationError(DomainError):
    """Credenciales inválidas o token expirado."""

    pass


class AuthService:
    """Servicio de autenticación sin estado.

    Este servicio es determinístico y no tiene dependencias en FastAPI ni Supabase.
    Para un caso real, la verificación de credenciales iría contra una tabla de usuarios
    en la base de datos.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        raw_secret = settings.SUPABASE_JWT_SECRET
        if raw_secret is None:
            self.jwt_secret = secrets.token_urlsafe(32)
        elif hasattr(raw_secret, "get_secret_value"):
            self.jwt_secret = raw_secret.get_secret_value()
        else:
            self.jwt_secret = str(raw_secret)

    def hash_password(self, password: str) -> str:
        """Hashea una contraseña con SHA256 + salt.

        Para producción, usar bcrypt o argon2.
        """
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return f"{salt}${hashed.hex()}"

    def verify_password(self, password: str, hash_value: str) -> bool:
        """Verifica una contraseña contra su hash.

        Usa constante-time comparison para evitar timing attacks.
        """
        try:
            salt, hashed = hash_value.split("$")
        except ValueError:
            return False

        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return secrets.compare_digest(computed.hex(), hashed)

    def create_tokens(
        self,
        user_id: str,
        email: str,
        name: str | None = None,
        avatar: str | None = None,
    ) -> TokenResponse:
        """Crea un pair de access + refresh tokens."""
        now = datetime.now(timezone.utc)
        access_expires_at = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_expires_at = now + timedelta(days=7)

        access_token_payload = {
            "sub": user_id,
            "email": email,
            "name": name,
            "avatar": avatar,
            "exp": access_expires_at,
            "iat": now,
            "type": "access",
        }

        refresh_token_payload = {
            "sub": user_id,
            "exp": refresh_expires_at,
            "iat": now,
            "type": "refresh",
        }

        access_token = jwt.encode(access_token_payload, self.jwt_secret, algorithm=JWT_ALGORITHM)
        refresh_token = jwt.encode(refresh_token_payload, self.jwt_secret, algorithm=JWT_ALGORITHM)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int((access_expires_at - now).total_seconds()),
        )

    def verify_token(self, token: str) -> dict:
        """Verifica y decodifica un JWT.

        Eleva AuthenticationError si el token es inválido o expirado.
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError as e:
            raise AuthenticationError("Token expirado") from e
        except jwt.InvalidTokenError as e:
            raise AuthenticationError("Token inválido") from e

    def get_current_user(self, token: str) -> CurrentUser:
        """Extrae el usuario del token.

        Eleva AuthenticationError si el token es inválido.
        """
        payload = self.verify_token(token)
        return CurrentUser(
            id=payload.get("sub", ""),
            email=payload.get("email", ""),
            name=payload.get("name"),
            avatar=payload.get("avatar"),
            roles=payload.get("roles", []),
        )

    def register(self, email: str, name: str, password: str) -> TokenResponse:
        """Registra un nuevo usuario.

        Para desarrollo/demo. En producción, iría contra una tabla en Supabase.
        """
        if not email or not name or not password:
            raise AuthenticationError("Email, nombre y contraseña son obligatorios")

        if "@" not in email:
            raise AuthenticationError("Email inválido")

        if len(password) < 8:
            raise AuthenticationError("La contraseña debe tener al menos 8 caracteres")

        if len(name.strip()) < 1:
            raise AuthenticationError("El nombre es obligatorio")

        # En producción:
        # 1. Verificar que el email no existe: SELECT * FROM users WHERE email = ?
        # 2. Hashear la contraseña
        # 3. INSERT INTO users (email, name, password_hash) VALUES (...)
        # Para demo, aceptamos el registro

        user_id = hashlib.sha256(email.encode()).hexdigest()[:16]
        return self.create_tokens(user_id=user_id, email=email, name=name)

    def login(self, email: str, password: str) -> TokenResponse:
        """Autentica un usuario verificando credenciales.

        Para desarrollo/demo. En producción, iría contra una tabla en Supabase.
        """
        # Para este demo, aceptamos cualquier credencial con formato válido
        # En realidad, aquí iría una query a la DB: SELECT * FROM users WHERE email = ?
        if not email or not password:
            raise AuthenticationError("Email y contraseña son obligatorios")

        if "@" not in email:
            raise AuthenticationError("Email inválido")

        # En producción:
        # user = SELECT * FROM users WHERE email = ?
        # if not user or not verify_password(password, user.password_hash):
        #     raise AuthenticationError("Email o contraseña incorrectos")
        # return self.create_tokens(user_id=user.id, email=user.email, name=user.name)

        # Usuario encontrado (simulado)
        user_id = hashlib.sha256(email.encode()).hexdigest()[:16]
        return self.create_tokens(user_id=user_id, email=email, name=email.split("@")[0])
