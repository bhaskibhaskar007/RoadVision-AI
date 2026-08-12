import logging
from pathlib import Path
import cv2, numpy as np
from app.config import settings
from app.services.severity import calculate_severity
logger = logging.getLogger(__name__)
class RoadDamageDetector:
    """YOLO wrapper. Demo mode intentionally returns no invented detections."""
    def __init__(self):
        self.model = None; self.available = False
        path = Path(settings.model_path)
        if not path.is_absolute(): path = Path(__file__).resolve().parents[2] / path
        if path.exists():
            try:
                from ultralytics import YOLO
                self.model = YOLO(str(path)); self.available = True; logger.info("Loaded road damage model: %s", path)
            except Exception: logger.exception("Model load failed")
        else: logger.warning("No trained road-damage weights at %s; running transparent empty demo mode", path)
    def infer(self, image: np.ndarray) -> list[dict]:
        if not self.available: return []
        result = self.model(image, conf=settings.confidence_threshold, iou=settings.iou_threshold, verbose=False)[0]
        height, width = image.shape[:2]; detections=[]
        for box in result.boxes:
            x1,y1,x2,y2 = [int(v) for v in box.xyxy[0].tolist()]; cls = result.names[int(box.cls[0])]; conf = round(float(box.conf[0]), 4)
            area=max(0,(x2-x1)*(y2-y1)); sev=calculate_severity(area,width*height,conf,cls)
            detections.append({"class_name":cls,"confidence":conf,"bbox":[x1,y1,x2,y2],"area_pixels":area,"severity":sev.label,"severity_score":sev.score})
        return detections
def draw_detections(image, detections):
    output=image.copy(); colors={"High":(48,80,220),"Medium":(20,160,240),"Low":(45,190,110)}
    for d in detections:
        x1,y1,x2,y2=d["bbox"]; color=colors[d["severity"]]; cv2.rectangle(output,(x1,y1),(x2,y2),color,2); cv2.putText(output,f"{d['class_name']} {d['confidence']:.0%} | {d['severity']}",(x1,max(20,y1-8)),cv2.FONT_HERSHEY_SIMPLEX,.5,color,2)
    return output
