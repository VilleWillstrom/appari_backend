# Appari Backend

Tiny REST adapter for Appari.

The backend exposes stable Appari API routes while the data currently comes
from Supabase. Later, the internal data source can be replaced without changing
the Flutter application's REST calls.

## Environment

Create a local `.env` file:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-key
CORS_ORIGINS=*
```

The `.env` file is intentionally ignored by Git.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
uvicorn main:app --reload
```

Default local URL:

```text
http://127.0.0.1:8000
```

## Endpoints

Health check:

```http
GET /
```

Route overview:

```http
GET /api/routes_overview
GET /api/routes_overview?weekday=1
```

Route detail:

```http
GET /api/routes/R001/details?weekday=1
GET /api/routes/R001/details?weekday=1&delivery_date=2026-05-07
```

The route detail endpoint returns delivery-date specific stop and container
quantities. When `delivery_date` is omitted, the backend uses the current date.
The cloud sync script refreshes today and tomorrow so container quantities stay
current without deleting older delivery days.

Route start event:

```http
POST /api/route_start_events
Content-Type: application/json

{
  "route_code": "R001",
  "weekday_index": 1,
  "started_at": "2026-05-07T12:30:00Z"
}
```

Delivery confirmation:

```http
POST /api/delivery_events
Content-Type: application/json

{
  "route_code": "R001",
  "delivery_date": "2026-05-07",
  "customer_number": "10001",
  "delivered_at": "2026-05-07T12:45:00Z",
  "latitude": 60.9821,
  "longitude": 25.6612
}
```

Weekday mapping:

- `1` = Monday
- `2` = Tuesday
- `3` = Wednesday
- `4` = Thursday
- `5` = Friday
- `6` = Saturday
- `7` = Sunday
