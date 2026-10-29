from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.database import init_db, seed_db
from app.exceptions import NotFoundError, ValidationError
from app.routes.order_routes import router as order_router
from app.routes.restaurant_routes import router as restaurant_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager that initializes tables and seeds initial data."""
    init_db()
    seed_db()
    yield


app = FastAPI(
    title="MiniDash",
    description="A lightweight food-delivery REST API built with FastAPI and SQLite.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


app.include_router(restaurant_router, prefix="/restaurants", tags=["restaurants"])
app.include_router(order_router, prefix="/orders", tags=["orders"])


@app.get("/", tags=["health"])
def health_check():
    return {"app": "MiniDash", "status": "ok"}
