"""
WSGI entry point for Render deployment.
Create the FastAPI app instance from factory.
"""
import os
import sys
from pathlib import Path

# Load .env if it exists
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

def create_app_safe():
    """Try to create the full app, fall back to minimal app on error."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    try:
        from app.core.config import Settings
        from app.main import create_app
        
        settings = Settings()
        app = create_app(settings)
        print("✓ Full app initialized")
        return app
        
    except Exception as e:
        # Fallback: minimal app that always works
        print(f"WARNING: Full app init failed: {e}", file=sys.stderr)
        
        app = FastAPI(
            title="Commitment Twin Backend",
            version="0.1.0"
        )
        
        @app.get("/")
        async def root():
            return {
                "service": "commitment-twin-backend",
                "status": "degraded",
                "error": str(e)
            }
        
        @app.get("/health")
        async def health():
            return {
                "status": "degraded",
                "message": "Configuration missing or invalid",
                "error": str(e)
            }
        
        return app

# Create app instance
try:
    app = create_app_safe()
except Exception as e:
    print(f"FATAL: Could not create app: {e}", file=sys.stderr)
    # Absolute fallback
    from fastapi import FastAPI
    app = FastAPI()
    
    @app.get("/")
    async def root():
        return {"error": "Failed to initialize app"}
