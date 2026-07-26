from supabase import create_client
from config import settings

client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

def get_supabase():
    return client
