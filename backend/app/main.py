from fastapi import FastAPI

from app.api import assets, auth, cabinets, components, dictionaries, export, health, imports, overview, rooms, search, users
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(cabinets.router)
app.include_router(assets.router)
app.include_router(components.router)
app.include_router(overview.router)
app.include_router(imports.router)
app.include_router(export.router)
app.include_router(search.router)
app.include_router(users.router)
app.include_router(dictionaries.router)
