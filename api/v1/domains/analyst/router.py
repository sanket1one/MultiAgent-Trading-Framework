from fastapi import APIRouter
from api.v1.domains.analyst import news, technical, fundametal, sentiment


analyst_router = APIRouter()

analyst_router.include_router(news.router, prefix="/news", tags=["News Analyst"])
analyst_router.include_router(technical.router, prefix="/technical", tags=["Technical Analyst"])
analyst_router.include_router(fundametal.router, prefix="/fundamental", tags=["Fundamental Analyst"])
analyst_router.include_router(sentiment.router, prefix="/sentiment", tags=["Sentiment Analyst"])