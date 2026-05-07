import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
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

cors_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class RouteStartEventRequest(BaseModel):
    route_code: str = Field(min_length=1)
    weekday_index: int = Field(ge=1, le=7)
    started_at: datetime


class RouteStartEventResponse(BaseModel):
    status: str
    route_code: str
    weekday_index: int
    started_at: datetime


def map_container(row: dict[str, Any]) -> dict[str, Any]:
    """Map route stop container JSON into the public Appari REST schema."""
    return {
        "container_code": row.get("container_code"),
        "container_name": row.get("container_name"),
        "quantity": row.get("quantity") or 0,
    }


def map_route_stop(row: dict[str, Any]) -> dict[str, Any]:
    """Map route stop JSON into the public Appari REST schema."""
    containers = row.get("containers")
    if not isinstance(containers, list):
        containers = []

    return {
        "position": row.get("position"),
        "customer_number": row.get("customer_number"),
        "stop_name": row.get("stop_name"),
        "address": row.get("address"),
        "instructions": row.get("instructions"),
        "extra_instructions": row.get("extra_instructions"),
        "containers": [
            map_container(item)
            for item in containers
            if isinstance(item, dict)
        ],
    }


def map_route_detail(row: dict[str, Any]) -> dict[str, Any]:
    """Map database-facing route detail JSON into the public REST schema."""
    stops = row.get("stops")
    if not isinstance(stops, list):
        stops = []

    return {
        "route_code": row.get("route_code"),
        "route_name": row.get("route_name"),
        "weekday_index": row.get("weekday_index"),
        "weekday_name": row.get("weekday_name"),
        "delivery_date": row.get("delivery_date"),
        "departure_time": row.get("departure_time"),
        "vehicle_number": row.get("vehicle_number"),
        "vehicle_name": row.get("vehicle_name"),
        "max_container": row.get("max_container") or 0,
        "stops": [
            map_route_stop(item)
            for item in stops
            if isinstance(item, dict)
        ],
    }


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


def map_route_start_event(row: dict[str, Any]) -> dict[str, Any]:
    """Map stored route start data into the public Appari REST schema."""
    return {
        "status": "ok",
        "route_code": row.get("route_code"),
        "weekday_index": row.get("weekday_index"),
        "started_at": row.get("started_at"),
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


@app.get("/api/routes/{route_code}/details")
def route_detail(
    route_code: str,
    weekday: int = Query(
        ge=1,
        le=7,
        description="Delivery weekday where 1 is Monday and 7 is Sunday.",
    ),
    delivery_date: str | None = Query(
        default=None,
        description=(
            "Delivery date in YYYY-MM-DD format. Defaults to the backend "
            "current date when omitted."
        ),
    ),
) -> dict[str, Any]:
    """Return one route with delivery-day specific stop and container data."""
    client = get_supabase_client()

    rpc_payload = {
        "p_route_code": route_code,
        "p_weekday_index": weekday,
    }
    if delivery_date is not None:
        rpc_payload["p_delivery_date"] = delivery_date

    try:
        response = client.rpc(
            "appari_get_route_detail",
            rpc_payload,
        ).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to load route detail from Supabase: {exc}",
        ) from exc

    if response.data is None:
        raise HTTPException(
            status_code=404,
            detail="Route detail was not found.",
        )

    if not isinstance(response.data, dict):
        raise HTTPException(
            status_code=502,
            detail="Supabase returned an unexpected route detail format.",
        )

    return map_route_detail(response.data)


@app.post(
    "/api/route_start_events",
    response_model=RouteStartEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_route_start_event(
    event: RouteStartEventRequest,
) -> dict[str, Any]:
    """Store a route start event sent by the Appari client."""
    client = get_supabase_client()

    payload = {
        "route_code": event.route_code,
        "weekday_index": event.weekday_index,
        "started_at": event.started_at.isoformat(),
    }

    try:
        response = (
            client.table("route_start_events")
            .insert(payload)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to store route start event in Supabase: {exc}",
        ) from exc

    if not response.data:
        raise HTTPException(
            status_code=502,
            detail="Supabase did not return the stored route start event.",
        )

    first_row = response.data[0]
    if not isinstance(first_row, dict):
        raise HTTPException(
            status_code=502,
            detail="Supabase returned an unexpected route start event format.",
        )

    return map_route_start_event(first_row)
