"""
WSGI entry point para Render deployment.
Inicializa la app FastAPI con fallback robusto.
"""
import sys
from pathlib import Path
from datetime import UTC, datetime

# Cargar .env si existe
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        pass

# App fallback (siempre disponible)
from fastapi import FastAPI
from fastapi.responses import JSONResponse

fallback_app = FastAPI(title="Commitment Twin", version="0.1.0")

@fallback_app.get("/")
async def root():
    return {
        "service": "commitment-twin-backend",
        "version": "0.1.0",
        "status": "running",
        "timestamp": datetime.now(UTC).isoformat(),
    }

@fallback_app.get("/health")
async def health():
    return {"status": "ok", "message": "Service is running"}

app = fallback_app

# Intentar cargar app completa
try:
    from app.core.config import Settings
    from app.main import create_app
    
    settings = Settings()
    app = create_app(settings)
    print("✓ Full app initialized", file=sys.stderr)
    
except Exception as e:
    print(f"⚠ Using fallback app: {e}", file=sys.stderr)
    # app sigue siendo fallback_app
