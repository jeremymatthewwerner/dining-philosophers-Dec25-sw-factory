"""API routes for Dining Philosophers."""

from fastapi import APIRouter

from app.api import admin, auth, conversations, sessions, spend, test_helpers, thinkers, websocket

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(thinkers.router, prefix="/thinkers", tags=["thinkers"])
api_router.include_router(spend.router, prefix="/spend", tags=["spend"])
api_router.include_router(test_helpers.router, tags=["test-helpers"])

# WebSocket route (no prefix - uses /ws/{conversation_id})
ws_router = websocket.router
