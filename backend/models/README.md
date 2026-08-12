# Model installation

Copy your trained custom YOLO road-damage weights to `backend/models/road_damage.pt`, or set `MODEL_PATH` in `backend/.env`. The classes must match `training/data.yaml`. Without weights, the application is deliberately in empty demo mode: it processes and stores images but returns no fabricated detections.
