import uuid
from pathlib import Path

import cv2
import numpy as np

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database.database import get_db
from app.models.entities import User, Inspection, Detection
from app.schemas.common import Credentials, Token
from app.services.detector import (
    RoadDamageDetector,
    draw_detections,
)
from app.services.report_generator import generate_report
from app.utils.security import (
    create_token,
    hash_password,
    token_subject,
    verify_password,
)


router = APIRouter(prefix="/api")

detector = RoadDamageDetector()


IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

VIDEO_TYPES = {
    "video/mp4",
    "video/x-msvideo",
    "video/quicktime",
    "video/x-matroska",
}


# ============================================================
# AUTHENTICATION
# ============================================================

def user_for(
    token=Depends(token_subject),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.email == token
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return user


# ============================================================
# INSPECTION RESPONSE
# ============================================================

def inspection_json(i):
    return {
        "id": i.id,
        "filename": i.filename,
        "input_type": i.input_type,
        "created_at": i.created_at,

        # GPS
        "latitude": i.latitude,
        "longitude": i.longitude,
        "location_accuracy": i.location_accuracy,

        # Detection summary
        "total_detections": i.total_detections,
        "highest_severity": i.highest_severity,

        # Result
        "result_url": (
            f"/api/files/results/{Path(i.result_path).name}"
            if i.result_path
            else None
        ),

        # PDF is generated lazily by GET /api/reports/{id}.
        "report_url": f"/api/reports/{i.id}",

        # Individual detections
        "detections": [
            {
                "class_name": d.class_name,
                "confidence": d.confidence,
                "bbox": [
                    d.x1,
                    d.y1,
                    d.x2,
                    d.y2,
                ],
                "area_pixels": d.area_pixels,
                "severity": d.severity,
            }
            for d in i.detections
        ],
    }


# ============================================================
# REGISTER
# ============================================================

@router.post(
    "/auth/register",
    response_model=Token,
)
def register(
    data: Credentials,
    db: Session = Depends(get_db),
):
    email = data.email.lower()

    if db.query(User).filter_by(
        email=email
    ).first():

        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    db.add(
        User(
            email=email,
            password_hash=hash_password(
                data.password
            ),
        )
    )

    db.commit()

    return Token(
        access_token=create_token(email)
    )


# ============================================================
# LOGIN
# ============================================================

@router.post(
    "/auth/login",
    response_model=Token,
)
def login(
    data: Credentials,
    db: Session = Depends(get_db),
):
    email = data.email.lower()

    user = db.query(User).filter_by(
        email=email
    ).first()

    if (
        not user
        or not verify_password(
            data.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )

    return Token(
        access_token=create_token(
            user.email
        )
    )


# ============================================================
# CURRENT USER
# ============================================================

@router.get("/auth/me")
def me(
    user=Depends(user_for),
):
    return {
        "id": user.id,
        "email": user.email,
    }


# ============================================================
# IMAGE DETECTION
# ============================================================

@router.post("/detection/image")
async def image_detection(
    file: UploadFile = File(...),

    # GPS
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    location_accuracy: float | None = Form(None),

    user=Depends(user_for),
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Validate image
    # --------------------------------------------------------

    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Use JPG, PNG, or WEBP image files",
        )

    # --------------------------------------------------------
    # Read file
    # --------------------------------------------------------

    payload = await file.read()

    if len(payload) > (
        settings.max_upload_size_mb * 1024 * 1024
    ):
        raise HTTPException(
            status_code=413,
            detail="Upload exceeds configured size limit",
        )

    # --------------------------------------------------------
    # Save original image
    # --------------------------------------------------------

    suffix = Path(
        file.filename or "image.jpg"
    ).suffix.lower()

    stem = uuid.uuid4().hex

    source = (
        settings.upload_dir /
        f"{stem}{suffix}"
    )

    source.write_bytes(payload)

    # --------------------------------------------------------
    # Decode image
    # --------------------------------------------------------

    image = cv2.imdecode(
        np.frombuffer(
            payload,
            dtype=np.uint8,
        ),
        cv2.IMREAD_COLOR,
    )

    if image is None:

        source.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=422,
            detail="Could not read this image",
        )

    # --------------------------------------------------------
    # YOLO inference
    # --------------------------------------------------------

    detections = detector.infer(image)

    # --------------------------------------------------------
    # Generate annotated image
    # --------------------------------------------------------

    output = (
        settings.results_dir /
        f"{stem}.jpg"
    )

    annotated = draw_detections(
        image,
        detections,
    )

    ok, encoded = cv2.imencode(
        ".jpg",
        annotated,
    )

    if not ok:
        raise HTTPException(
            status_code=500,
            detail="Could not create result image",
        )

    output.write_bytes(
        encoded.tobytes()
    )

    # --------------------------------------------------------
    # Highest severity
    # --------------------------------------------------------

    highest = next(
        (
            severity
            for severity in [
                "High",
                "Medium",
                "Low",
            ]
            if any(
                d["severity"] == severity
                for d in detections
            )
        ),
        "None",
    )

    # --------------------------------------------------------
    # Save inspection + GPS
    # --------------------------------------------------------

    inspection = Inspection(
        user_id=user.id,

        filename=(
            file.filename
            or source.name
        ),

        input_type="image",

        total_detections=len(
            detections
        ),

        highest_severity=highest,

        result_path=str(output),

        # GPS
        latitude=latitude,
        longitude=longitude,
        location_accuracy=location_accuracy,
    )

    db.add(inspection)

    db.flush()

    # --------------------------------------------------------
    # Save detections
    # --------------------------------------------------------

    for d in detections:

        db.add(
            Detection(
                inspection_id=inspection.id,
                class_name=d["class_name"],
                confidence=d["confidence"],
                x1=d["bbox"][0],
                y1=d["bbox"][1],
                x2=d["bbox"][2],
                y2=d["bbox"][3],
                area_pixels=d["area_pixels"],
                severity=d["severity"],
            )
        )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    db.commit()

    db.refresh(inspection)

    return {
        **inspection_json(inspection),

        "model_available":
            detector.available,

        "demo_notice": (
            None
            if detector.available
            else
            "No trained road-damage weights are installed."
        ),
    }


# ============================================================
# LIVE CAMERA
# ============================================================

@router.post("/detection/live")
async def live(
    file: UploadFile = File(...),

    # GPS from browser
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    location_accuracy: float | None = Form(None),

    user=Depends(user_for),
    db: Session = Depends(get_db),
):
    return await image_detection(
        file=file,
        latitude=latitude,
        longitude=longitude,
        location_accuracy=location_accuracy,
        user=user,
        db=db,
    )


# ============================================================
# VIDEO DETECTION
# ============================================================

@router.post("/detection/video")
async def video_detection(
    file: UploadFile = File(...),

    # GPS from browser
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    location_accuracy: float | None = Form(None),

    user=Depends(user_for),
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # Validate video
    # --------------------------------------------------------

    if file.content_type not in VIDEO_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Use MP4, AVI, MOV, or MKV video files",
        )

    payload = await file.read()

    if len(payload) > (
        settings.max_upload_size_mb *
        1024 *
        1024
    ):
        raise HTTPException(
            status_code=413,
            detail="Upload exceeds configured size limit",
        )

    # --------------------------------------------------------
    # Save video
    # --------------------------------------------------------

    suffix = Path(
        file.filename or "video.mp4"
    ).suffix.lower()

    stem = uuid.uuid4().hex

    source = (
        settings.upload_dir /
        f"{stem}{suffix}"
    )

    source.write_bytes(payload)

    # --------------------------------------------------------
    # Open video
    # --------------------------------------------------------

    cap = cv2.VideoCapture(
        str(source)
    )

    if not cap.isOpened():
        raise HTTPException(
            status_code=422,
            detail="Could not read this video",
        )

    fps = (
        cap.get(cv2.CAP_PROP_FPS)
        or 24
    )

    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    output = (
        settings.results_dir /
        f"{stem}.mp4"
    )

    writer = cv2.VideoWriter(
        str(output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    count = 0
    total = 0
    confidence_sum = 0.0

    severity = {
        "Low": 0,
        "Medium": 0,
        "High": 0,
    }

    classes = {}
    all_found = []

    # --------------------------------------------------------
    # Process frames
    # --------------------------------------------------------

    while True:

        ok, frame = cap.read()

        if not ok:
            break

        count += 1

        if (
            count %
            settings.process_every_n_frames
            == 0
        ):
            found = detector.infer(
                frame
            )
        else:
            found = []

        writer.write(
            draw_detections(
                frame,
                found,
            )
        )

        for d in found:

            total += 1

            confidence_sum += (
                d["confidence"]
            )

            severity[
                d["severity"]
            ] += 1

            classes[
                d["class_name"]
            ] = (
                classes.get(
                    d["class_name"],
                    0,
                )
                + 1
            )

            all_found.append(d)

    cap.release()
    writer.release()

    # --------------------------------------------------------
    # Highest severity
    # --------------------------------------------------------

    highest = next(
        (
            s
            for s in [
                "High",
                "Medium",
                "Low",
            ]
            if severity[s]
        ),
        "None",
    )

    # --------------------------------------------------------
    # Save inspection + GPS
    # --------------------------------------------------------

    inspection = Inspection(
        user_id=user.id,

        filename=(
            file.filename
            or source.name
        ),

        input_type="video",

        total_detections=total,

        highest_severity=highest,

        result_path=str(output),

        # GPS
        latitude=latitude,
        longitude=longitude,
        location_accuracy=location_accuracy,
    )

    db.add(inspection)

    db.flush()

    # --------------------------------------------------------
    # Save detections
    # --------------------------------------------------------

    for d in all_found:

        db.add(
            Detection(
                inspection_id=inspection.id,
                class_name=d["class_name"],
                confidence=d["confidence"],
                x1=d["bbox"][0],
                y1=d["bbox"][1],
                x2=d["bbox"][2],
                y2=d["bbox"][3],
                area_pixels=d["area_pixels"],
                severity=d["severity"],
            )
        )

    db.commit()

    db.refresh(inspection)

    return {
        **inspection_json(inspection),

        "frame_count": count,

        "average_confidence": (
            round(
                confidence_sum / total,
                3,
            )
            if total
            else 0
        ),

        "categories": classes,

        "severity_statistics":
            severity,

        "model_available":
            detector.available,

        "demo_notice": (
            None
            if detector.available
            else
            "No trained road-damage weights are installed."
        ),
    }


# ============================================================
# INSPECTION HISTORY
# ============================================================

@router.get("/inspections")
def inspections(
    skip: int = 0,
    limit: int = 20,
    user=Depends(user_for),
    db: Session = Depends(get_db),
):

    items = (
        db.query(Inspection)
        .filter_by(
            user_id=user.id
        )
        .order_by(
            Inspection.created_at.desc()
        )
        .offset(skip)
        .limit(
            min(limit, 100)
        )
        .all()
    )

    return [
        inspection_json(i)
        for i in items
    ]


# ============================================================
# INSPECTION DETAILS
# ============================================================

@router.get(
    "/inspections/{inspection_id}"
)
def detail(
    inspection_id: int,
    user=Depends(user_for),
    db: Session = Depends(get_db),
):

    inspection = (
        db.query(Inspection)
        .filter_by(
            id=inspection_id,
            user_id=user.id,
        )
        .first()
    )

    if not inspection:
        raise HTTPException(
            status_code=404,
            detail="Inspection not found",
        )

    return inspection_json(
        inspection
    )


# ============================================================
# DELETE INSPECTION
# ============================================================

@router.delete(
    "/inspections/{inspection_id}",
    status_code=204,
)
def delete_inspection(
    inspection_id: int,
    user=Depends(user_for),
    db: Session = Depends(get_db),
):

    inspection = (
        db.query(Inspection)
        .filter_by(
            id=inspection_id,
            user_id=user.id,
        )
        .first()
    )

    if not inspection:
        raise HTTPException(
            status_code=404,
            detail="Inspection not found",
        )

    db.delete(inspection)

    db.commit()


# ============================================================
# PDF REPORT
# ============================================================

@router.get(
    "/reports/{inspection_id}"
)
def report(
    inspection_id: int,
    user=Depends(user_for),
    db: Session = Depends(get_db),
):

    inspection = (
        db.query(Inspection)
        .filter_by(
            id=inspection_id,
            user_id=user.id,
        )
        .first()
    )

    if not inspection:
        raise HTTPException(
            status_code=404,
            detail="Inspection not found",
        )

    if not inspection.report_path:

        path = (
            settings.reports_dir /
            f"inspection-{inspection.id}.pdf"
        )

        generate_report(
            path,
            inspection,
            inspection.detections,
            inspection.result_path,
        )

        inspection.report_path = str(path)

        db.commit()

    return FileResponse(
        inspection.report_path,
        media_type="application/pdf",
        filename=(
            f"roadvision-inspection-"
            f"{inspection.id}.pdf"
        ),
    )


# ============================================================
# DASHBOARD STATISTICS
# ============================================================

@router.get(
    "/dashboard/statistics"
)
def statistics(
    user=Depends(user_for),
    db: Session = Depends(get_db),
):

    query = (
        db.query(Inspection)
        .filter_by(
            user_id=user.id
        )
    )

    inspections_list = query.all()

    ids = [
        i.id
        for i in inspections_list
    ]

    detections = (
        db.query(Detection)
        .filter(
            Detection.inspection_id.in_(
                ids
            )
        )
        .all()
        if ids
        else []
    )

    types = {}

    severities = {
        "Low": 0,
        "Medium": 0,
        "High": 0,
    }

    for d in detections:

        types[d.class_name] = (
            types.get(
                d.class_name,
                0,
            )
            + 1
        )

        severities[d.severity] = (
            severities.get(
                d.severity,
                0,
            )
            + 1
        )

    # Supports Pothole/Pothole and pothole/pothole
    potholes = sum(
        value
        for key, value in types.items()
        if key.lower() == "pothole"
    )

    cracks = sum(
        value
        for key, value in types.items()
        if "crack" in key.lower()
    )

    return {
        "total_inspections":
            len(inspections_list),

        "total_damages":
            len(detections),

        "potholes":
            potholes,

        "cracks":
            cracks,

        "high_severity":
            severities["High"],

        "average_confidence": (
            round(
                sum(
                    d.confidence
                    for d in detections
                )
                / len(detections),
                3,
            )
            if detections
            else 0
        ),

        "types": types,

        "severities": severities,
    }


# ============================================================
# RESULT FILE
# ============================================================

@router.get(
    "/files/results/{name}"
)
def result_file(
    name: str,
):

    path = (
        settings.results_dir /
        Path(name).name
    )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Result not found",
        )

    return FileResponse(path)