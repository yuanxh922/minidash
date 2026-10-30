from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

STATIC_INDEX_PATH = Path(__file__).resolve().parent.parent / "static" / "index.html"


def get_frontend_html() -> str:
    """Read the frontend HTML document from disk."""
    if STATIC_INDEX_PATH.is_file():
        return STATIC_INDEX_PATH.read_text(encoding="utf-8")
    return "<h1>MiniDash UI</h1><p>Frontend template not found.</p>"


@router.get("/ui", response_class=HTMLResponse, tags=["frontend"])
@router.get("/dashboard", response_class=HTMLResponse, tags=["frontend"])
def get_dashboard_page():
    """Serve the MiniDash single-page frontend application."""
    return HTMLResponse(content=get_frontend_html())
