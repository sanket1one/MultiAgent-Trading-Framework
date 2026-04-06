from fastapi import APIRouter
from . import execution

trader_router = APIRouter()

trader_router.include_router(execution.router, prefix="/execution")
