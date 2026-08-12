from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
def generate_report(path: Path, inspection, detections: list, image_path: str | None):
    c=canvas.Canvas(str(path), pagesize=A4); width,height=A4; y=height-2*cm
    c.setFont("Helvetica-Bold",18); c.drawString(2*cm,y,"ROADVISION AI"); y-=.8*cm
    c.setFont("Helvetica-Bold",13); c.drawString(2*cm,y,"ROAD DAMAGE INSPECTION REPORT"); y-=1*cm
    c.setFont("Helvetica",10)
    for line in [f"Inspection ID: {inspection.id}",f"Date: {inspection.created_at:%Y-%m-%d %H:%M}",f"Input file: {inspection.filename}",f"Total detected damages: {len(detections)}", "Severity is an approximate pixel-based estimate; no real-world area is claimed."]:
        c.drawString(2*cm,y,line); y-=.55*cm
    y-=.3*cm; c.setFont("Helvetica-Bold",11); c.drawString(2*cm,y,"Detections"); y-=.6*cm; c.setFont("Helvetica",9)
    for d in detections:
        c.drawString(2*cm,y,f"{d.class_name} | confidence {d.confidence:.0%} | {d.severity} | {d.area_pixels} px²")
        y-=.45*cm
        if y<4*cm: c.showPage(); y=height-2*cm
    if image_path and Path(image_path).exists():
        y-=.4*cm; c.setFont("Helvetica-Bold",11); c.drawString(2*cm,y,"Annotated result"); y-=.4*cm
        try: c.drawImage(image_path,2*cm,max(2*cm,y-10*cm),width=16*cm,height=9*cm,preserveAspectRatio=True,anchor='n')
        except Exception: pass
    c.save()
