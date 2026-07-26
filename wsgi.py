"""
WSGI entry point para Render deployment.
Maneja todos los casos de error y siempre devuelve una app funcional.
"""
import sys
import os
import traceback
from pathlib import Path
from datetime import datetime

# Load .env if exists
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

# Initialize as fallback first
from fastapi import FastAPI

fallback_app = FastAPI(
    title="Commitment Twin Backend",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Store errors for reporting
startup_errors = []

@fallback_app.get("/")
async def root():
    return {
        "service": "commitment-twin-backend",
        "status": "error" if startup_errors else "ok",
        "version": "0.1.0",
        "errors": startup_errors if startup_errors else None,
        "timestamp": datetime.utcnow().isoformat()
    }

@fallback_app.get("/health")
async def health():
    return {
        "status": "degraded" if startup_errors else "ok",
        "message": startup_errors[0] if startup_errors else "Running",
    }

app = fallback_app

# Try to load the real app
try:
    from app.core.config import Settings
    from app.main import create_app
    
    settings = Settings()
    app = create_app(settings)
    print("✓ Full app initialized successfully", file=sys.stderr)
    
except Exception as e:
    error_msg = f"{type(e).__name__}: {str(e)}"
    print(f"WARNING: Could not initialize full app: {error_msg}", file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    startup_errors.append(error_msg)
    # app is already set to fallback_app above
