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
from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

# Add project root to path so we can import computation_engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.advisor import get_advice, search_market
from backend.data_fetch_http import clear_caches, fetch_land_object
from backend.excel_generator import generate_excel
from backend.geocode import find_parcel_at_coords, parse_coordinates
from backend.intake import extract_fields, merge_document_and_geoportal, parse_docx, resolve_coordinates
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

class LocationRequest(BaseModel):
    query: str  # Google Maps URL, coordinates, or parcel ID


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

@app.post("/api/intake")
async def intake_document(file: UploadFile) -> dict:
    """Parse a .docx land opportunity and return extracted + Geoportal data."""
    if not _http_client or not _anthropic:
        raise HTTPException(500, "Server not ready")

    if not file.filename or not file.filename.endswith(".docx"):
        raise HTTPException(400, "Only .docx files are supported")

    try:
        # 1. Parse docx
        file_bytes = await file.read()
        text = parse_docx(file_bytes)
        log.info("Parsed docx: %d chars", len(text))

        # 2. Extract fields via Claude
        extracted = await extract_fields(text, _anthropic)
        log.info("Extracted: %s", {k: v for k, v in extracted.items() if k != "survey_coordinates"})

        # 3. Resolve coordinates
        coords = await resolve_coordinates(extracted, _http_client)
        log.info("Coordinates: %s", coords)

        # 4. Find parcel in Geoportal
        geoportal_data = None
        if coords:
            lat, lng = coords
            parcel_info = await find_parcel_at_coords(_http_client, lat, lng)
            if parcel_info and parcel_info.get("parcel_id"):
                try:
                    geoportal_data = await fetch_land_object(_http_client, parcel_info["parcel_id"])
                except Exception as exc:
                    log.warning("Geoportal fetch failed: %s", exc)
                    geoportal_data = {"parcel_summary": parcel_info}

        # 5. Merge
        merged = merge_document_and_geoportal(extracted, geoportal_data)

        return {
            "extracted": extracted,
            "coordinates": {"lat": coords[0], "lng": coords[1]} if coords else None,
            "geoportal": geoportal_data,
            "merged": merged,
            "conflicts": merged.get("conflicts", []),
            "document_text_preview": text[:500],
        }

    except HTTPException:
        raise
    except Exception as exc:
        log.error("Intake error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.post("/api/locate")
async def locate_parcel(req: LocationRequest) -> dict:
    """Find a parcel from a Google Maps URL, coordinates, or parcel ID.

    Accepts:
      - Google Maps URL: https://www.google.com/maps/place/...@24.648,46.658...
      - Coordinates: "24.648843, 46.658778"
      - Parcel ID: "3834663"
    """
    if not _http_client:
        raise HTTPException(500, "Server not ready")

    query = req.query.strip()

    # Try as parcel ID first
    try:
        pid = int(query)
        if pid > 100000:  # looks like a parcel ID
            land = await fetch_land_object(_http_client, pid)
            if land.get("parcel_number"):
                return {"source": "parcel_id", "parcel_id": pid, "land_object": land}
    except ValueError:
        pass

    # Try as coordinates or Google Maps URL
    coords = parse_coordinates(query)
    if not coords:
        raise HTTPException(400, "Could not parse location. Paste a Google Maps link or coordinates (lat, lng).")

    lat, lng = coords
    log.info("Parsed coordinates: lat=%.6f, lng=%.6f", lat, lng)

    # Find parcel at those coordinates
    result = await find_parcel_at_coords(_http_client, lat, lng)
    if not result or not result.get("parcel_id"):
        raise HTTPException(404, f"No parcel found at ({lat:.6f}, {lng:.6f}). The location may be outside Riyadh's parcel database.")

    parcel_id = result["parcel_id"]
    log.info("Found parcel %s at coordinates", parcel_id)

    # Fetch full land object
    land = await fetch_land_object(_http_client, parcel_id)
    return {
        "source": "coordinates",
        "coordinates": {"lat": lat, "lng": lng},
        "parcel_id": parcel_id,
        "parcel_summary": result,
        "land_object": land,
    }


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
        if not land.get("parcel_id"):
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


class ExcelRequest(BaseModel):
    parcel_id: int
    overrides: dict[str, Any] = {}
    lang: str = "ar"


@app.post("/api/excel")
async def download_excel_post(req: ExcelRequest) -> Response:
    """Generate and download .xlsx pro-forma with full overrides (POST)."""
    if not _http_client:
        raise HTTPException(500, "Server not ready")
    try:
        land = await fetch_land_object(_http_client, req.parcel_id)
        if not land.get("parcel_id"):
            raise HTTPException(404, f"Parcel {req.parcel_id} not found")

        result = compute_proforma(land, req.overrides)
        xlsx_bytes = generate_excel(result, land, req.overrides, lang=req.lang)

        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="proforma_{req.parcel_id}.xlsx"',
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Excel error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.get("/api/excel/{parcel_id}")
async def download_excel(
    parcel_id: int,
    lang: str = Query("ar"),
) -> Response:
    """Generate and download .xlsx pro-forma (GET fallback, uses defaults)."""
    if not _http_client:
        raise HTTPException(500, "Server not ready")
    try:
        land = await fetch_land_object(_http_client, parcel_id)
        if not land.get("parcel_id"):
            raise HTTPException(404, f"Parcel {parcel_id} not found")

        overrides: dict[str, Any] = {}

        result = compute_proforma(land, overrides)
        xlsx_bytes = generate_excel(result, land, overrides, lang=lang)

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
