"""
WSGI entry point for Render deployment.
Render can't easily call factory functions, so we create the app instance here.
"""
import sys
from pathlib import Path

# Asegurar que el .env se carga si existe
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

from app.core.config import Settings
from app.main import create_app

try:
    settings = Settings()
    app = create_app(settings)
except Exception as e:
    print(f"ERROR inicializando app: {e}", file=sys.stderr)
    # En case de error, devolver una app mínima que responda 500
    from fastapi import FastAPI
    app = FastAPI()
    
    @app.get("/health")
    def health_error():
        return {"status": "error", "message": str(e)}
