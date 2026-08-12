# Architecture

The React client sends authenticated image/camera frames to FastAPI. The API validates and stores source files, keeps a singleton `RoadDamageDetector` in memory, persists results through SQLAlchemy, and serves annotated images and ReportLab PDFs. SQLite is configured by default; change `DATABASE_URL` to a PostgreSQL SQLAlchemy URL for production.

Severity is transparent and approximate: bounding-box pixel area relative to the image, model confidence, and a configurable type weight are combined. It is not a measurement of physical damage area.
