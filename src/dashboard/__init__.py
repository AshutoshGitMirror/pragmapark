from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

from src.api.server import app

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(templates_dir):
    templates = Jinja2Templates(directory=templates_dir)
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/driver", response_class=HTMLResponse)
async def driver_dashboard(request: Request):
    return templates.TemplateResponse("driver.html", {"request": request})
