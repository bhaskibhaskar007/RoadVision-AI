from dataclasses import dataclass
@dataclass
class SeverityResult: score: int; label: str
TYPE_WEIGHT = {"pothole": 28, "alligator_crack": 24, "longitudinal_crack": 14, "transverse_crack": 14}
def calculate_severity(area_pixels: int, image_area: int, confidence: float, class_name: str) -> SeverityResult:
    ratio = area_pixels / max(image_area, 1)
    score = min(45, int(ratio * 500)) + int(confidence * 25) + TYPE_WEIGHT.get(class_name, 12)
    score = min(100, score); label = "High" if score >= 66 else "Medium" if score >= 31 else "Low"
    return SeverityResult(score, label)
