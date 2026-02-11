"""FastAPI backend wiring data_fetch + computation_engine + advisor + excel.

Run: uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

import httpx
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

# Add project root to path so we can import computation_engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.advisor import get_advice, search_market
from backend.data_fetch_http import clear_caches, fetch_land_object
from backend.excel_generator import generate_excel
from computation_engine import compute_proforma

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger("api")

# ---------------------------------------------------------------------------
# Lifespan: manage httpx client and Anthropic client
# ---------------------------------------------------------------------------

_http_client: httpx.AsyncClient | None = None
_anthropic: AsyncAnthropic | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client, _anthropic
    _http_client = httpx.AsyncClient(verify=False, follow_redirects=True)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        _anthropic = AsyncAnthropic(api_key=api_key)
        log.info("Anthropic client initialized")
    else:
        log.warning("ANTHROPIC_API_KEY not set — advisor endpoints will fail")
    log.info("Server started")
    yield
    await _http_client.aclose()
    log.info("Server stopped")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="KSA Estate API",
    description="Riyadh real estate parcel analysis, pro-forma, and AI advisor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class ProformaRequest(BaseModel):
    parcel_id: int
    overrides: dict[str, Any] = {}


class ScenarioItem(BaseModel):
    name: str
    overrides: dict[str, Any] = {}


class ScenarioRequest(BaseModel):
    parcel_id: int
    base_overrides: dict[str, Any] = {}
    scenarios: list[ScenarioItem]


class AdvisorRequest(BaseModel):
    parcel_id: int
    proforma: dict[str, Any] | None = None
    question: str


class SearchRequest(BaseModel):
    parcel_id: int
    query: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/parcel/{parcel_id}")
async def get_parcel(parcel_id: int) -> dict:
    """Fetch Land Object for a parcel (geometry, zoning, regulations, market)."""
    if not _http_client:
        raise HTTPException(500, "Server not ready")
    try:
        land = await fetch_land_object(_http_client, parcel_id)
        if not land.get("parcel_number"):
            raise HTTPException(404, f"Parcel {parcel_id} not found")
        return land
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Parcel fetch error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.post("/api/proforma")
async def run_proforma(req: ProformaRequest) -> dict:
    """Fetch parcel + compute full pro-forma."""
    if not _http_client:
        raise HTTPException(500, "Server not ready")
    try:
        land = await fetch_land_object(_http_client, req.parcel_id)
        if not land.get("parcel_number"):
            raise HTTPException(404, f"Parcel {req.parcel_id} not found")
        result = compute_proforma(land, req.overrides)
        return {"land_object": land, "proforma": result}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Proforma error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.post("/api/proforma/scenario")
async def run_scenarios(req: ScenarioRequest) -> dict:
    """Run multiple scenarios for comparison."""
    if not _http_client:
        raise HTTPException(500, "Server not ready")
    try:
        land = await fetch_land_object(_http_client, req.parcel_id)
        if not land.get("parcel_number"):
            raise HTTPException(404, f"Parcel {req.parcel_id} not found")

        results = []
        for scenario in req.scenarios:
            merged = {**req.base_overrides, **scenario.overrides}
            pf = compute_proforma(land, merged)
            results.append({
                "name": scenario.name,
                "overrides": merged,
                "proforma": pf,
            })

        return {"land_object": land, "scenarios": results}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Scenario error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.post("/api/advisor")
async def advisor(req: AdvisorRequest) -> dict:
    """Get AI-powered strategic advice."""
    if not _anthropic:
        raise HTTPException(503, "Anthropic API not configured")
    if not _http_client:
        raise HTTPException(500, "Server not ready")
    try:
        land = await fetch_land_object(_http_client, req.parcel_id)
        result = await get_advice(_anthropic, land, req.proforma, req.question)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Advisor error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.post("/api/advisor/search")
async def advisor_search(req: SearchRequest) -> dict:
    """Market intelligence search."""
    if not _anthropic:
        raise HTTPException(503, "Anthropic API not configured")
    if not _http_client:
        raise HTTPException(500, "Server not ready")
    try:
        land = await fetch_land_object(_http_client, req.parcel_id)
        result = await search_market(_anthropic, land, req.query)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Search error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.get("/api/excel/{parcel_id}")
async def download_excel(
    parcel_id: int,
    land_price_per_sqm: float | None = Query(None),
    sale_price_per_sqm: float | None = Query(None),
    fund_period_years: int | None = Query(None),
) -> Response:
    """Generate and download .xlsx pro-forma."""
    if not _http_client:
        raise HTTPException(500, "Server not ready")
    try:
        land = await fetch_land_object(_http_client, parcel_id)
        if not land.get("parcel_number"):
            raise HTTPException(404, f"Parcel {parcel_id} not found")

        overrides: dict[str, Any] = {}
        if land_price_per_sqm is not None:
            overrides["land_price_per_sqm"] = land_price_per_sqm
        if sale_price_per_sqm is not None:
            overrides["sale_price_per_sqm"] = sale_price_per_sqm
        if fund_period_years is not None:
            overrides["fund_period_years"] = fund_period_years

        result = compute_proforma(land, overrides)
        xlsx_bytes = generate_excel(result, land)

        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="proforma_{parcel_id}.xlsx"',
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Excel error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.post("/api/cache/clear")
async def clear_cache() -> dict:
    """Clear all caches (admin/debug)."""
    clear_caches()
    return {"status": "cleared"}


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "anthropic": _anthropic is not None,
        "http_client": _http_client is not None,
    }
