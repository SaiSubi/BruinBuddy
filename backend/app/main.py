"""FastAPI app: accounts, courses and memberships, billing, materials, chats, assignments, dashboard.

Each course is a tenant. Routes check an active membership in the course (courses.get_member) before touching
anything in it; roles come only from memberships."""
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import accounts, assignments, billing, chats, config, courses, dashboard, materials, members
from .db import init_db

_google = {"at": 0.0, "enabled": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.check_production_settings()
    init_db()
    materials.recover_interrupted()
    yield


app = FastAPI(title="BruinBuddy", lifespan=lifespan,
              docs_url=None if config.PRODUCTION else "/docs", redoc_url=None,
              openapi_url=None if config.PRODUCTION else "/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                   allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"], max_age=600)
for module in (accounts, courses, members, billing, materials, chats, assignments, dashboard):
    app.include_router(module.router)


def _google_enabled() -> bool:
    """Whether Google sign-in is switched on in Supabase (checked at most every 10 minutes)."""
    if config.AUTH_PROVIDER != "supabase":
        return False
    if time.time() - _google["at"] > 600:
        try:
            r = httpx.get(f"{config.SUPABASE_URL}/auth/v1/settings", headers={"apikey": config.SUPABASE_ANON_KEY}, timeout=5)
            _google["enabled"] = bool(r.json().get("external", {}).get("google"))
        except (httpx.HTTPError, ValueError):
            _google["enabled"] = False
        _google["at"] = time.time()
    return _google["enabled"]


@app.get("/api/config")
def public_config():
    supabase = config.AUTH_PROVIDER == "supabase"
    return {"auth": {"provider": config.AUTH_PROVIDER,
                     "supabase_url": config.SUPABASE_URL if supabase else "",
                     "supabase_anon_key": config.SUPABASE_ANON_KEY if supabase else "",  # public by design
                     "google": _google_enabled()},
            "billing": {"mode": config.billing_mode()},
            "plans": billing.plan_options(),
            "upload": {"max_mb": config.MAX_UPLOAD_BYTES // (1024 * 1024), "types": list(materials.TYPES)}}


@app.get("/api/health")
def health():
    return {"ok": True, "llm": "mock" if config.MOCK_LLM else ("ready" if config.OPENROUTER_API_KEY else "no_key"),
            "auth": config.AUTH_PROVIDER, "billing": config.billing_mode()}


if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")
