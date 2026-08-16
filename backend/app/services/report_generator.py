from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def generate_report(
    path: Path,
    inspection,
    detections: list,
    image_path: str | None,
):
    """
    Generate a professional RoadVision AI inspection PDF.

    Includes:
    - Inspection information
    - GPS location
    - Google Maps link
    - Detection summary
    - Individual detections
    - Annotated result image
    """

    c = canvas.Canvas(
        str(path),
        pagesize=A4,
    )

    width, height = A4
    y = height - 2 * cm

    # ============================================================
    # HELPERS
    # ============================================================

    def new_page():
        nonlocal y

        c.showPage()
        y = height - 2 * cm

    def ensure_space(required_height=2 * cm):
        nonlocal y

        if y < required_height:
            new_page()

    # ============================================================
    # HEADER
    # ============================================================

    c.setFillColor(colors.HexColor("#0B1F26"))
    c.setFont("Helvetica-Bold", 20)

    c.drawString(
        2 * cm,
        y,
        "ROADVISION AI",
    )

    y -= 0.8 * cm

    c.setFillColor(colors.HexColor("#20C9A6"))
    c.setFont("Helvetica-Bold", 13)

    c.drawString(
        2 * cm,
        y,
        "ROAD DAMAGE INSPECTION REPORT",
    )

    y -= 1.2 * cm

    # ============================================================
    # INSPECTION INFORMATION
    # ============================================================

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)

    c.drawString(
        2 * cm,
        y,
        "Inspection Information",
    )

    y -= 0.65 * cm

    c.setFont("Helvetica", 10)

    inspection_date = getattr(
        inspection,
        "created_at",
        None,
    )

    if inspection_date:
        formatted_date = inspection_date.strftime(
            "%Y-%m-%d %H:%M"
        )
    else:
        formatted_date = "N/A"

    information = [
        f"Inspection ID: {inspection.id}",
        f"Date: {formatted_date}",
        f"Input file: {inspection.filename}",
        f"Input type: {inspection.input_type}",
        f"Total detected damages: {len(detections)}",
    ]

    for line in information:
        ensure_space()

        c.drawString(
            2 * cm,
            y,
            line,
        )

        y -= 0.5 * cm

    y -= 0.3 * cm

    # ============================================================
    # GPS LOCATION
    # ============================================================

    ensure_space(8 * cm)

    latitude = getattr(
        inspection,
        "latitude",
        None,
    )

    longitude = getattr(
        inspection,
        "longitude",
        None,
    )

    accuracy = getattr(
        inspection,
        "location_accuracy",
        None,
    )

    # Location box
    c.setFillColor(colors.HexColor("#0B1F26"))

    c.roundRect(
        2 * cm,
        y - 4.7 * cm,
        17 * cm,
        4.5 * cm,
        0.25 * cm,
        fill=1,
        stroke=0,
    )

    # Location title
    c.setFillColor(colors.HexColor("#20C9A6"))
    c.setFont("Helvetica-Bold", 12)

    c.drawString(
        2.5 * cm,
        y - 0.7 * cm,
        "INSPECTION LOCATION",
    )

    # Coordinates
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 10)

    if latitude is not None:
        c.drawString(
            2.5 * cm,
            y - 1.5 * cm,
            f"Latitude: {latitude:.6f}",
        )
    else:
        c.drawString(
            2.5 * cm,
            y - 1.5 * cm,
            "Latitude: Not available",
        )

    if longitude is not None:
        c.drawString(
            2.5 * cm,
            y - 2.1 * cm,
            f"Longitude: {longitude:.6f}",
        )
    else:
        c.drawString(
            2.5 * cm,
            y - 2.1 * cm,
            "Longitude: Not available",
        )

    if accuracy is not None:
        c.drawString(
            2.5 * cm,
            y - 2.7 * cm,
            f"GPS Accuracy: +/- {accuracy:.0f} m",
        )
    else:
        c.drawString(
            2.5 * cm,
            y - 2.7 * cm,
            "GPS Accuracy: Not available",
        )

    # Google Maps
    if latitude is not None and longitude is not None:

        maps_url = (
            "https://www.google.com/maps/search/"
            f"?api=1&query={latitude},{longitude}"
        )

        c.setFillColor(
            colors.HexColor("#20C9A6")
        )

        c.setFont(
            "Helvetica-Bold",
            9,
        )

        c.drawString(
            2.5 * cm,
            y - 3.5 * cm,
            "Open inspection location in Google Maps",
        )

        c.linkURL(
            maps_url,
            (
                2.5 * cm,
                y - 3.65 * cm,
                11.5 * cm,
                y - 3.3 * cm,
            ),
            relative=0,
        )

    else:

        c.setFillColor(
            colors.HexColor("#AAAAAA")
        )

        c.setFont(
            "Helvetica",
            9,
        )

        c.drawString(
            2.5 * cm,
            y - 3.5 * cm,
            "GPS location was not available for this inspection.",
        )

    y -= 5.2 * cm

    # ============================================================
    # DETECTION SUMMARY
    # ============================================================

    ensure_space(6 * cm)

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)

    c.drawString(
        2 * cm,
        y,
        "Detection Summary",
    )

    y -= 0.7 * cm

    c.setFont("Helvetica", 10)

    c.drawString(
        2 * cm,
        y,
        f"Total detections: {len(detections)}",
    )

    y -= 0.5 * cm

    highest_severity = getattr(
        inspection,
        "highest_severity",
        "None",
    )

    c.drawString(
        2 * cm,
        y,
        f"Highest severity: {highest_severity}",
    )

    y -= 0.5 * cm

    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#555555"))

    c.drawString(
        2 * cm,
        y,
        "Severity is an approximate pixel-based estimate; "
        "no real-world area is claimed.",
    )

    y -= 0.9 * cm

    # ============================================================
    # DETECTIONS
    # ============================================================

    ensure_space(6 * cm)

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)

    c.drawString(
        2 * cm,
        y,
        "Detected Road Damage",
    )

    y -= 0.7 * cm

    c.setFont("Helvetica-Bold", 9)

    c.drawString(
        2 * cm,
        y,
        "Type",
    )

    c.drawString(
        7 * cm,
        y,
        "Confidence",
    )

    c.drawString(
        10 * cm,
        y,
        "Severity",
    )

    c.drawString(
        13 * cm,
        y,
        "Area",
    )

    y -= 0.35 * cm

    c.line(
        2 * cm,
        y,
        18.5 * cm,
        y,
    )

    y -= 0.45 * cm

    c.setFont("Helvetica", 9)

    if detections:

        for detection in detections:

            ensure_space(3 * cm)

            c.drawString(
                2 * cm,
                y,
                str(detection.class_name),
            )

            c.drawString(
                7 * cm,
                y,
                f"{detection.confidence:.0%}",
            )

            c.drawString(
                10 * cm,
                y,
                str(detection.severity),
            )

            c.drawString(
                13 * cm,
                y,
                f"{detection.area_pixels:,} px²",
            )

            y -= 0.55 * cm

    else:

        c.drawString(
            2 * cm,
            y,
            "No road damage detected.",
        )

        y -= 0.55 * cm

    # ============================================================
    # ANNOTATED IMAGE
    # ============================================================

    if image_path and Path(image_path).exists():

        ensure_space(12 * cm)

        y -= 0.4 * cm

        c.setFont(
            "Helvetica-Bold",
            12,
        )

        c.setFillColor(colors.black)

        c.drawString(
            2 * cm,
            y,
            "Annotated Inspection Result",
        )

        y -= 0.5 * cm

        try:

            c.drawImage(
                image_path,
                2 * cm,
                max(
                    2 * cm,
                    y - 10 * cm,
                ),
                width=16 * cm,
                height=9 * cm,
                preserveAspectRatio=True,
                anchor="n",
            )

        except Exception:
            pass

    # ============================================================
    # FOOTER
    # ============================================================

    c.setFillColor(
        colors.HexColor("#777777")
    )

    c.setFont(
        "Helvetica",
        7.5,
    )

    c.drawString(
        2 * cm,
        1.2 * cm,
        "Generated by RoadVision AI - Road Damage Inspection System",
    )

    c.save()