"""Vercel detects this ASGI FastAPI app under project root backend/."""
from fleetluma_backend.cloud_api import create_cloud_app

app = create_cloud_app()
