# API

Interactive API documentation is served by FastAPI at `/docs` and `/redoc`.

Protected endpoints use `Authorization: Bearer <token>`: `POST /api/detection/image`, `POST /api/detection/live`, `GET /api/inspections`, `GET /api/reports/{id}`, and `GET /api/dashboard/statistics`.
