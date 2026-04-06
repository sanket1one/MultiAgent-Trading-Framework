from fastapi import APIRouter
from . import news, technical, fundametal


analyst_router = APIRouter()


analyst_router.include_router(news.router, prefix="/news")
analyst_router.include_router(technical.router, prefix="/technical")
analyst_router.include_router(fundametal.router, prefix="/fundametal")