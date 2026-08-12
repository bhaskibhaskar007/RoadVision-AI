from pathlib import Path
from ultralytics import YOLO
model=YOLO('runs/roadvision/train/weights/best.pt'); print(model.val(data=str(Path(__file__).with_name('data.yaml'))))
