import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from supabase import Client, create_client


load_dotenv()


app = FastAPI(
    title="Appari Backend",
    version="0.1.0",
    description=(
        "A small REST adapter that keeps Appari client calls stable while "
        "the current data source is Supabase."
    ),
)


def get_supabase_client() -> Client:
    """Create a Supabase client from the local backend environment."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL and SUPABASE_KEY must be configured.",
        )

    try:
        return create_client(supabase_url, supabase_key)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize Supabase client: {exc}",
        ) from exc


def normalize_rpc_payload(payload: Any) -> list[dict[str, Any]]:
    """Normalize Supabase RPC responses into a predictable list of routes."""
    if payload is None:
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        routes = payload.get("routes")
        if isinstance(routes, list):
            return [item for item in routes if isinstance(item, dict)]
        return [payload]

    return []


def map_route(row: dict[str, Any]) -> dict[str, Any]:
    """Map the database-facing route JSON into the public Appari REST schema."""
    return {
        "route_code": row.get("route_code"),
        "route_name": row.get("route_name"),
        "weekday_index": row.get("weekday_index"),
        "weekday_name": row.get("weekday_name"),
        "packing_day_index": row.get("packing_day_index"),
        "departure_time": row.get("departure_time"),
        "vehicle_number": row.get("vehicle_number"),
        "vehicle_name": row.get("vehicle_name"),
        "max_container": row.get("max_container"),
        "active_customer_count": row.get("active_customer_count"),
    }


@app.get("/")
def index() -> dict[str, str]:
    """Return a tiny health response for local backend checks."""
    return {"service": "appari_backend", "status": "ok"}


@app.get("/api/routes_overview")
def routes_overview(
    weekday: int | None = Query(
        default=None,
        ge=1,
        le=7,
        description="Optional delivery weekday where 1 is Monday and 7 is Sunday.",
    )
) -> dict[str, Any]:
    """Return weekly route cards using the stable Appari REST response shape."""
    client = get_supabase_client()

    try:
        response = client.rpc(
            "appari_get_weekly_routes",
            {"p_weekday_index": weekday},
        ).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to load route overview from Supabase: {exc}",
        ) from exc

    routes = [map_route(row) for row in normalize_rpc_payload(response.data)]

    return {
        "weekday_index": weekday,
        "routes": routes,
    }
