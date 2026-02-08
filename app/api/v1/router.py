"""
Main API v1 router that aggregates all route modules.
"""

from fastapi import APIRouter

from app.api.v1 import auth, domains, ratings, user, stats

# Create main v1 router
api_router = APIRouter(prefix="/v1")

# Include sub-routers (ratings before domains so /domains/rating matches before /domains/{id})
api_router.include_router(auth.router)
api_router.include_router(ratings.router)
api_router.include_router(domains.router)
api_router.include_router(user.router)
api_router.include_router(stats.router)
