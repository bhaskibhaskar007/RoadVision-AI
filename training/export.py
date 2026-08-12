from ultralytics import YOLO
model=YOLO('runs/roadvision/train/weights/best.pt'); model.export(format='onnx')
