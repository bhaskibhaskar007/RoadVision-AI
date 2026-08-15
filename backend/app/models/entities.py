from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True
    )

    password_hash: Mapped[str] = mapped_column(
        String(255)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    inspections: Mapped[list["Inspection"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )

    # ==========================================
    # GPS LOCATION
    # ==========================================

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    location_accuracy: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    # ==========================================
    # INSPECTION INFORMATION
    # ==========================================

    filename: Mapped[str] = mapped_column(
        String(255)
    )

    input_type: Mapped[str] = mapped_column(
        String(20)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    total_detections: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    highest_severity: Mapped[str] = mapped_column(
        String(20),
        default="None"
    )

    result_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    report_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    # ==========================================
    # RELATIONSHIPS
    # ==========================================

    user: Mapped["User"] = relationship(
        back_populates="inspections"
    )

    detections: Mapped[list["Detection"]] = relationship(
        back_populates="inspection",
        cascade="all, delete-orphan"
    )


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id")
    )

    class_name: Mapped[str] = mapped_column(
        String(80)
    )

    confidence: Mapped[float] = mapped_column(
        Float
    )

    x1: Mapped[int] = mapped_column(
        Integer
    )

    y1: Mapped[int] = mapped_column(
        Integer
    )

    x2: Mapped[int] = mapped_column(
        Integer
    )

    y2: Mapped[int] = mapped_column(
        Integer
    )

    area_pixels: Mapped[int] = mapped_column(
        Integer
    )

    severity: Mapped[str] = mapped_column(
        String(20)
    )

    inspection: Mapped["Inspection"] = relationship(
        back_populates="detections"
    )