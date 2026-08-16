import ast
import json
import logging
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from app.config import settings
from app.services.severity import calculate_severity

logger = logging.getLogger(__name__)


class RoadDamageDetector:
    """
    Lightweight YOLO ONNX detector.

    Production inference uses ONNX Runtime instead of
    Ultralytics/PyTorch to reduce RAM usage.
    """

    def __init__(self):
        self.session = None
        self.available = False
        self.input_name = None
        self.input_width = 416
        self.input_height = 416
        self.class_names = {}

        try:
            configured_path = Path(settings.model_path)

            if not configured_path.is_absolute():
                configured_path = (
                    Path(__file__).resolve().parents[2] / configured_path
                )

            # Prefer ONNX automatically.
            if configured_path.suffix.lower() == ".onnx":
                onnx_path = configured_path
            else:
                onnx_path = configured_path.with_suffix(".onnx")

            # Fallback: explicitly check backend/models/best.onnx
            if not onnx_path.exists():
                fallback = (
                    Path(__file__).resolve().parents[2]
                    / "models"
                    / "best.onnx"
                )

                if fallback.exists():
                    onnx_path = fallback

            if not onnx_path.exists():
                logger.warning(
                    "No ONNX model found. Expected model at: %s",
                    onnx_path,
                )
                return

            # Keep ONNX Runtime lightweight for small servers.
            session_options = ort.SessionOptions()
            session_options.intra_op_num_threads = 1
            session_options.inter_op_num_threads = 1
            session_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )

            self.session = ort.InferenceSession(
                str(onnx_path),
                sess_options=session_options,
                providers=["CPUExecutionProvider"],
            )

            input_meta = self.session.get_inputs()[0]
            self.input_name = input_meta.name

            # Read model input dimensions.
            input_shape = input_meta.shape

            if (
                len(input_shape) == 4
                and isinstance(input_shape[2], int)
                and isinstance(input_shape[3], int)
            ):
                self.input_height = input_shape[2]
                self.input_width = input_shape[3]

            self._load_class_names()

            self.available = True

            logger.info(
                "Loaded ONNX road damage model: %s",
                onnx_path,
            )

            logger.info(
                "ONNX input: %sx%s",
                self.input_width,
                self.input_height,
            )

            logger.info(
                "Classes: %s",
                self.class_names,
            )

        except Exception:
            logger.exception("ONNX model load failed")
            self.session = None
            self.available = False

    # ------------------------------------------------------------------
    # MODEL CLASS NAMES
    # ------------------------------------------------------------------

    def _load_class_names(self):
        """
        Ultralytics exports class names into ONNX metadata.
        This method supports several possible metadata formats.
        """

        try:
            metadata = self.session.get_modelmeta()
            custom = metadata.custom_metadata_map or {}

            names_value = custom.get("names")

            if not names_value:
                return

            # Try JSON first.
            try:
                parsed = json.loads(names_value)
            except Exception:
                parsed = None

            # Try Python literal representation.
            if parsed is None:
                try:
                    parsed = ast.literal_eval(names_value)
                except Exception:
                    parsed = None

            if isinstance(parsed, dict):
                self.class_names = {
                    int(k): str(v) for k, v in parsed.items()
                }

            elif isinstance(parsed, list):
                self.class_names = {
                    i: str(name) for i, name in enumerate(parsed)
                }

            logger.info(
                "Loaded %d class names from ONNX metadata",
                len(self.class_names),
            )

        except Exception:
            logger.warning(
                "Could not read class names from ONNX metadata"
            )

    # ------------------------------------------------------------------
    # LETTERBOX
    # ------------------------------------------------------------------

    @staticmethod
    def _letterbox(
        image: np.ndarray,
        new_width: int,
        new_height: int,
    ):
        """
        Resize image while preserving aspect ratio.
        Returns resized image, scale and padding.
        """

        original_height, original_width = image.shape[:2]

        scale = min(
            new_width / original_width,
            new_height / original_height,
        )

        resized_width = int(round(original_width * scale))
        resized_height = int(round(original_height * scale))

        resized = cv2.resize(
            image,
            (resized_width, resized_height),
            interpolation=cv2.INTER_LINEAR,
        )

        pad_width = new_width - resized_width
        pad_height = new_height - resized_height

        left = pad_width // 2
        right = pad_width - left

        top = pad_height // 2
        bottom = pad_height - top

        padded = cv2.copyMakeBorder(
            resized,
            top,
            bottom,
            left,
            right,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )

        return padded, scale, left, top

    # ------------------------------------------------------------------
    # PREPROCESS
    # ------------------------------------------------------------------

    def _preprocess(self, image: np.ndarray):
        """
        Convert OpenCV BGR image to YOLO ONNX input.
        """

        padded, scale, pad_x, pad_y = self._letterbox(
            image,
            self.input_width,
            self.input_height,
        )

        # BGR -> RGB
        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)

        # uint8 -> float32
        tensor = rgb.astype(np.float32) / 255.0

        # HWC -> CHW
        tensor = np.transpose(tensor, (2, 0, 1))

        # Add batch dimension
        tensor = np.expand_dims(tensor, axis=0)

        return tensor, scale, pad_x, pad_y

    # ------------------------------------------------------------------
    # OUTPUT PROCESSING
    # ------------------------------------------------------------------

    def _process_output(
        self,
        output: np.ndarray,
        image_width: int,
        image_height: int,
        scale: float,
        pad_x: int,
        pad_y: int,
    ):
        """
        Convert YOLO ONNX predictions into project detections.
        """

        output = np.asarray(output)

        # Remove batch dimension.
        if output.ndim == 3:
            output = output[0]

        if output.ndim != 2:
            logger.error(
                "Unexpected ONNX output shape: %s",
                output.shape,
            )
            return []

        # Ultralytics YOLO exports commonly return:
        # [channels, predictions]
        #
        # Example:
        # [84, 8400]
        #
        # Convert to:
        # [8400, 84]
        if output.shape[0] < output.shape[1]:
            output = output.T

        num_predictions = output.shape[0]
        num_values = output.shape[1]

        if num_values < 5:
            logger.error(
                "Invalid YOLO output shape: %s",
                output.shape,
            )
            return []

        # Determine whether model has objectness.
        #
        # Modern Ultralytics detection:
        # 4 box values + class scores
        #
        # Older YOLO:
        # 4 box values + objectness + class scores
        num_classes_from_metadata = len(self.class_names)

        if num_classes_from_metadata > 0:
            modern_values = 4 + num_classes_from_metadata
            old_values = 5 + num_classes_from_metadata

            if num_values == old_values:
                has_objectness = True
                num_classes = num_classes_from_metadata
            else:
                has_objectness = False
                num_classes = num_classes_from_metadata
        else:
            # Your exported Ultralytics model is expected to use
            # the modern 4 + class_scores format.
            has_objectness = False
            num_classes = num_values - 4

        if num_classes <= 0:
            return []

        detections = []

        confidence_threshold = float(
            settings.confidence_threshold
        )

        iou_threshold = float(
            settings.iou_threshold
        )

        # --------------------------------------------------------------
        # Extract candidates
        # --------------------------------------------------------------

        candidates = []

        for row in output:
            cx, cy, width, height = row[:4]

            if has_objectness:
                objectness = float(row[4])
                class_scores = row[5:5 + num_classes]

                class_id = int(np.argmax(class_scores))
                class_confidence = float(class_scores[class_id])

                confidence = objectness * class_confidence

            else:
                class_scores = row[4:4 + num_classes]

                class_id = int(np.argmax(class_scores))
                confidence = float(class_scores[class_id])

            if confidence < confidence_threshold:
                continue

            # YOLO xywh -> padded image xyxy
            x1 = cx - width / 2
            y1 = cy - height / 2
            x2 = cx + width / 2
            y2 = cy + height / 2

            # Remove letterbox padding.
            x1 = (x1 - pad_x) / scale
            y1 = (y1 - pad_y) / scale
            x2 = (x2 - pad_x) / scale
            y2 = (y2 - pad_y) / scale

            # Clamp to original image.
            x1 = max(0, min(image_width - 1, x1))
            y1 = max(0, min(image_height - 1, y1))
            x2 = max(0, min(image_width - 1, x2))
            y2 = max(0, min(image_height - 1, y2))

            box_width = x2 - x1
            box_height = y2 - y1

            if box_width <= 1 or box_height <= 1:
                continue

            candidates.append(
                {
                    "class_id": class_id,
                    "confidence": confidence,
                    "box": [
                        float(x1),
                        float(y1),
                        float(box_width),
                        float(box_height),
                    ],
                }
            )

        if not candidates:
            return []

        # --------------------------------------------------------------
        # Class-aware NMS
        # --------------------------------------------------------------

        final_candidates = []

        class_ids = sorted(
            set(item["class_id"] for item in candidates)
        )

        for class_id in class_ids:
            class_items = [
                item
                for item in candidates
                if item["class_id"] == class_id
            ]

            boxes = [
                item["box"]
                for item in class_items
            ]

            scores = [
                float(item["confidence"])
                for item in class_items
            ]

            indices = cv2.dnn.NMSBoxes(
                boxes,
                scores,
                confidence_threshold,
                iou_threshold,
            )

            if indices is None or len(indices) == 0:
                continue

            indices = np.array(indices).reshape(-1)

            for index in indices:
                final_candidates.append(
                    class_items[int(index)]
                )

        # --------------------------------------------------------------
        # Convert to project format
        # --------------------------------------------------------------

        detections = []

        for item in final_candidates:
            class_id = item["class_id"]
            confidence = round(
                float(item["confidence"]),
                4,
            )

            x, y, w, h = item["box"]

            x1 = int(round(x))
            y1 = int(round(y))
            x2 = int(round(x + w))
            y2 = int(round(y + h))

            class_name = self.class_names.get(
                class_id,
                str(class_id),
            )

            area = max(
                0,
                (x2 - x1) * (y2 - y1),
            )

            severity = calculate_severity(
                area,
                image_width * image_height,
                confidence,
                class_name,
            )

            detections.append(
                {
                    "class_name": class_name,
                    "confidence": confidence,
                    "bbox": [
                        x1,
                        y1,
                        x2,
                        y2,
                    ],
                    "area_pixels": area,
                    "severity": severity.label,
                    "severity_score": severity.score,
                }
            )

        return detections

    # ------------------------------------------------------------------
    # INFERENCE
    # ------------------------------------------------------------------

    def infer(self, image: np.ndarray) -> list[dict]:
        """
        Run ONNX inference on one OpenCV image.
        """

        if not self.available or self.session is None:
            return []

        if image is None or image.size == 0:
            logger.warning("Received empty image")
            return []

        try:
            image_height, image_width = image.shape[:2]

            tensor, scale, pad_x, pad_y = self._preprocess(
                image
            )

            outputs = self.session.run(
                None,
                {
                    self.input_name: tensor,
                },
            )

            if not outputs:
                return []

            detections = self._process_output(
                outputs[0],
                image_width,
                image_height,
                scale,
                pad_x,
                pad_y,
            )

            logger.info(
                "ONNX inference complete: %d detections",
                len(detections),
            )

            return detections

        except Exception:
            logger.exception("ONNX inference failed")
            return []


# ----------------------------------------------------------------------
# DRAW DETECTIONS
# ----------------------------------------------------------------------

def draw_detections(image, detections):
    output = image.copy()

    colors = {
        "High": (48, 80, 220),
        "Medium": (20, 160, 240),
        "Low": (45, 190, 110),
    }

    for detection in detections:
        x1, y1, x2, y2 = detection["bbox"]

        color = colors.get(
            detection["severity"],
            (255, 255, 255),
        )

        cv2.rectangle(
            output,
            (x1, y1),
            (x2, y2),
            color,
            2,
        )

        label = (
            f"{detection['class_name']} "
            f"{detection['confidence']:.0%} | "
            f"{detection['severity']}"
        )

        cv2.putText(
            output,
            label,
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
        )

    return output