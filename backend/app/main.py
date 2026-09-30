from fastapi import FastAPI

from app.api import assets, auth, cabinets, components, health, rooms
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(cabinets.router)
app.include_router(assets.router)
app.include_router(components.router)
