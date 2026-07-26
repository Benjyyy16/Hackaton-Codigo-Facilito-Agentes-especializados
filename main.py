from fastapi import FastAPI
from db import get_supabase

app = FastAPI(title="Backend Hackaton")

@app.on_event("startup")
async def startup():
    sb = get_supabase()
    print("✓ Supabase connected")

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
