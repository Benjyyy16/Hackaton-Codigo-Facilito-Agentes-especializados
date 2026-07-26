"""Configuración de la aplicación.

Toda la configuración proviene del entorno. Los secretos se declaran como ``SecretStr``
para que su representación por defecto los ofusque: registrar el objeto ``Settings`` en un
log no filtra credenciales (RF-1.4, RNF-1.1).

La ausencia de una variable obligatoria detiene el arranque en lugar de asumir un valor por
defecto silencioso (RF-1.2).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import StrEnum

APP_NAME: Final[str] = "commitment-twin-backend"
APP_VERSION: Final[str] = "0.1.0"


class Environment(StrEnum):
    """Entorno de ejecución."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LogLevel(StrEnum):
    """Niveles de log admitidos."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ConfigurationError(RuntimeError):
    """La configuración es inválida o está incompleta.

    Se eleva en el arranque. El mensaje nombra las variables afectadas pero nunca incluye
    sus valores (RF-1.2).
    """


class Settings(BaseSettings):
    """Configuración cargada desde el entorno y, si existe, desde un archivo ``.env``.

    El entorno real del proceso tiene precedencia sobre el archivo, que es el
    comportamiento por defecto de ``pydantic-settings``.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Supabase -----------------------------------------------------------------
    # El backend escribe como servicio de confianza y necesita saltarse RLS, de ahí el uso
    # de la clave de service role. Esa clave nunca sale en una respuesta de la API
    # (RNF-1.2). La clave anónima queda reservada para el futuro flujo con JWT de usuario.
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: SecretStr
    SUPABASE_ANON_KEY: SecretStr | None = None
    SUPABASE_JWT_SECRET: SecretStr | None = None

    # --- Jira ---------------------------------------------------------------------
    JIRA_BASE_URL: str | None = None
    JIRA_EMAIL: str | None = None
    JIRA_API_TOKEN: SecretStr | None = None
    JIRA_WEBHOOK_SECRET: SecretStr | None = None

    # --- GitHub -------------------------------------------------------------------
    GITHUB_TOKEN: SecretStr | None = None
    GITHUB_WEBHOOK_SECRET: SecretStr | None = None
    GITHUB_ORG: str | None = None

    # --- Slack --------------------------------------------------------------------
    SLACK_BOT_TOKEN: SecretStr | None = None
    SLACK_WEBHOOK_URL: str | None = None
    SLACK_CHANNEL: str | None = "#alerts"

    # --- Vercel -------------------------------------------------------------------
    VERCEL_TOKEN: SecretStr | None = None
    VERCEL_TEAM_ID: str | None = None

    # --- Notion -------------------------------------------------------------------
    NOTION_TOKEN: SecretStr | None = None
    NOTION_DATABASE_ID: str | None = None

    # --- OAuth apps (para flujo OAuth de usuarios externos) ---------------------
    APP_BASE_URL: str = "https://hackaton-codigo-facilito-agentes.onrender.com"
    FRONTEND_URL: str = "https://hackaton-codigo-facilito-agentes-especializados.vercel.app"
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: SecretStr | None = None
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: SecretStr | None = None
    NOTION_CLIENT_ID: str | None = None
    NOTION_CLIENT_SECRET: SecretStr | None = None
    SLACK_CLIENT_ID: str | None = None
    SLACK_CLIENT_SECRET: SecretStr | None = None
    VERCEL_CLIENT_ID: str | None = None
    VERCEL_CLIENT_SECRET: SecretStr | None = None

    # --- OpenAI -------------------------------------------------------------------
    OPENAI_API_KEY: SecretStr | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=120)

    # --- Demo mode ----------------------------------------------------------------
    #: Habilita rutas /demo/* en cualquier entorno (incluido production).
    #: Sin esta bandera, solo funcionan en development/test.
    DEMO_MODE_ENABLED: bool = False

    # --- Arranque del esquema -----------------------------------------------------
    # Cadena de conexion de Postgres. NO es la clave de servicio: la clave habla con
    # PostgREST, que no ejecuta DDL. Solo se usa para aplicar db/schema.sql.
    SUPABASE_DB_URL: SecretStr | None = None
    # Sin este token, POST /admin/schema/apply responde 404. Ejecutar DDL desde HTTP
    # requiere una autorizacion explicita, no la ausencia de una prohibicion.
    SCHEMA_BOOTSTRAP_TOKEN: SecretStr | None = None

    # --- Reglas de negocio --------------------------------------------------------
    RISK_ALERT_THRESHOLD: int = Field(default=70, ge=0, le=100)

    # --- Cliente HTTP -------------------------------------------------------------
    HTTP_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0, le=120)
    HTTP_MAX_RETRIES: int = Field(default=3, ge=0, le=10)

    # --- Servicio -----------------------------------------------------------------
    ENV: Environment = Environment.DEVELOPMENT
    LOG_LEVEL: LogLevel = LogLevel.INFO

    @field_validator("SUPABASE_URL")
    @classmethod
    def _require_supabase_url(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate.startswith(("http://", "https://")):
            raise ValueError("debe ser un URL absoluto que empiece por http:// o https://")
        return candidate.rstrip("/")

    @field_validator("JIRA_BASE_URL", "SLACK_WEBHOOK_URL")
    @classmethod
    def _validate_http_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        if not candidate.startswith(("http://", "https://")):
            raise ValueError("debe ser un URL absoluto que empiece por http:// o https://")
        return candidate.rstrip("/")

    @field_validator("JIRA_EMAIL")
    @classmethod
    def _require_email_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        if "@" not in candidate:
            raise ValueError("debe ser una dirección de correo")
        return candidate

    @property
    def is_production(self) -> bool:
        return self.ENV is Environment.PRODUCTION

    @property
    def app_name(self) -> str:
        return APP_NAME

    @property
    def app_version(self) -> str:
        return APP_VERSION


def _describe_validation_error(error: ValidationError) -> str:
    """Convierte un error de validación en un mensaje que nombra campos, nunca valores.

    ``ValidationError`` de Pydantic incluye por defecto la entrada que falló. Para
    configuración eso significa volcar secretos en el log de arranque, así que aquí solo se
    conservan el nombre del campo y el motivo (RF-1.2).
    """
    problems: list[str] = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "(raíz)"
        if item["type"] == "missing":
            problems.append(f"{location}: variable de entorno obligatoria ausente")
        else:
            problems.append(f"{location}: {item['msg']}")
    joined = "; ".join(problems)
    return f"Configuración inválida -> {joined}"


def load_settings(**overrides: object) -> Settings:
    """Construye ``Settings`` traduciendo cualquier fallo a ``ConfigurationError``.

    ``overrides`` se pasa tal cual a ``Settings``. Existe para que los tests puedan
    desactivar la lectura de archivos con ``_env_file=None`` y ser herméticos; en
    producción se llama sin argumentos.

    La cadena de excepciones se corta con ``from None`` a propósito: la traza de
    ``ValidationError`` incluye los valores de entrada, y volcarla en el log de arranque
    filtraría secretos.
    """
    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as error:
        raise ConfigurationError(_describe_validation_error(error)) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración del proceso, resuelta una sola vez.

    La caché evita releer el entorno en cada petición. Los tests la invalidan con
    ``get_settings.cache_clear()``.
    """
    return load_settings()
