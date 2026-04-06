from fastapi import APIRouter
from api.v1.domains.analyst.router import analyst_router
from api.v1.domains.trader.router import trader_router


api_v1_router = APIRouter()

api_v1_router.include_router(analyst_router, prefix="/analyst", tags=["Analyst"])
api_v1_router.include_router(trader_router, prefix="/trader", tags=["Trader"])