from fastapi import APIRouter

from app.api import auth, cron, dashboard, health, invoices, messages, public, settings, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(invoices.router)
api_router.include_router(messages.router)
api_router.include_router(settings.router)
api_router.include_router(users.router)
api_router.include_router(public.router)
api_router.include_router(cron.router)
