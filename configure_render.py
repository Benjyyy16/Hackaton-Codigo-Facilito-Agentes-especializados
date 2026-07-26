#!/usr/bin/env python3
"""
Configure environment variables in Render via API.

Usage:
  1. Export RENDER_API_KEY from https://dashboard.render.com/account/api-keys
  2. Run: python3 configure_render.py
"""

import os
import json
import sys
from pathlib import Path

# Render API details
RENDER_API_BASE = "https://api.render.com/v1"
SERVICE_ID = "dep-d9ibr7av4c73b6ip6g"  # Your deployment ID

def configure_render_env():
    """Set environment variables in Render service."""
    api_key = os.getenv("RENDER_API_KEY")
    if not api_key:
        print("ERROR: RENDER_API_KEY not set")
        print("Get it from: https://dashboard.render.com/account/api-keys")
        return False
    
    # Load env vars from .render-env.json
    render_env_file = Path(__file__).parent / ".render-env.json"
    if not render_env_file.exists():
        print(f"ERROR: {render_env_file} not found")
        return False
    
    with open(render_env_file) as f:
        env_vars = json.load(f)
    
    print(f"Will configure {len(env_vars)} environment variables in Render")
    print(f"Service ID: {SERVICE_ID}")
    
    # This would require the render API python client
    # For now, just show instructions
    print("\nTo apply these via Render dashboard:")
    print("1. Go to: https://dashboard.render.com/services/" + SERVICE_ID)
    print("2. Click 'Environment' tab")
    print("3. For each variable below, click 'Add Environment Variable':")
    
    for key, value in env_vars.items():
        if "KEY" in key or "TOKEN" in key:
            print(f"   {key}=<paste-actual-secret-here>")
        else:
            print(f"   {key}={value}")
    
    print("\n4. Click 'Save'")
    print("5. Click 'Redeploy latest commit'")

if __name__ == "__main__":
    configure_render_env()
