
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import asyncio


from .main import run_agent

app = FastAPI()


BASE_DIR = Path(__file__).parent

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

# ==================================================
# Request Model
# ==================================================

class ChatRequest(BaseModel):
    query: str
    user_context: Optional[Dict[str, Any]] = None


# ==================================================
# Health
# ==================================================

@app.get("/health")
async def health():
    return {"status": "ok"}


# ==================================================
# Home Page
# ==================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


# ==================================================
# Chat Endpoint
# ==================================================

@app.post("/chat")
async def chat(req: ChatRequest):

    result = await asyncio.to_thread(
        run_agent,
        req.query,
        req.user_context
    )

    return {
        "response": result
    }