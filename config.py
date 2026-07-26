from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str
    FASTAPI_ENV: str = "development"
    FASTAPI_DEBUG: bool = True
    
    class Config:
        env_file = ".env.local"

settings = Settings()
