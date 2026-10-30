from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import init_db, seed_db
from app.exceptions import NotFoundError, ValidationError
from app.routes.frontend_routes import router as frontend_router, get_frontend_html
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


app.include_router(frontend_router)
app.include_router(restaurant_router, prefix="/restaurants", tags=["restaurants"])
app.include_router(order_router, prefix="/orders", tags=["orders"])


@app.get("/", tags=["health"])
def health_check(request: Request):
    """Health check endpoint. Serves frontend HTML if requested by a web browser."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse(content=get_frontend_html())
    return {"app": "MiniDash", "status": "ok"}


@app.get("/health", tags=["health"])
def explicit_health_check():
    """Explicit JSON health check endpoint."""
    return {"app": "MiniDash", "status": "ok"}
