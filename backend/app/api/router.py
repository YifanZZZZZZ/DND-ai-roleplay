from fastapi import APIRouter

from backend.app.api.routes import campaigns, characters, events, messages, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(characters.router)
api_router.include_router(campaigns.router)
api_router.include_router(messages.router)
api_router.include_router(events.router)
