"""
WSGI entry point for Render deployment.
Create the FastAPI app instance from factory.
"""
import os
import sys
from pathlib import Path
from fastapi import FastAPI

# Load .env if it exists
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

# For debugging
print(f"ENV vars present: SUPABASE_URL={bool(os.getenv('SUPABASE_URL'))}, JIRA_BASE_URL={bool(os.getenv('JIRA_BASE_URL'))}")

try:
    from app.core.config import Settings
    from app.main import create_app
    
    settings = Settings()
    app = create_app(settings)
    print("✓ App successfully initialized with full configuration")
    
except Exception as e:
    print(f"ERROR initializing app: {e}", file=sys.stderr)
    
    # Fallback: minimal app
    app = FastAPI(
        title="Commitment Twin Backend",
        description="Fallback mode - configuration incomplete"
    )
    
    @app.get("/health")
    def health():
        return {"status": "error", "message": str(e)}
    
    @app.get("/")
    def root():
        return {"service": "commitment-twin-backend", "status": "error"}
