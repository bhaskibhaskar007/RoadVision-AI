import shutil, uuid
from pathlib import Path
import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import settings
from app.database.database import get_db
from app.models.entities import User, Inspection, Detection
from app.schemas.common import Credentials, Token
from app.services.detector import RoadDamageDetector, draw_detections
from app.services.report_generator import generate_report
from app.utils.security import create_token, hash_password, token_subject, verify_password
router=APIRouter(prefix="/api"); detector=RoadDamageDetector()
IMAGE_TYPES={"image/jpeg","image/png","image/webp"}; VIDEO_TYPES={"video/mp4","video/x-msvideo","video/quicktime","video/x-matroska"}
def user_for(token=Depends(token_subject), db: Session=Depends(get_db)):
    user=db.query(User).filter(User.email==token).first()
    if not user: raise HTTPException(401,"User not found")
    return user
def inspection_json(i):
    return {"id":i.id,"filename":i.filename,"input_type":i.input_type,"created_at":i.created_at,"total_detections":i.total_detections,"highest_severity":i.highest_severity,"result_url":f"/api/files/results/{Path(i.result_path).name}" if i.result_path else None,"report_url":f"/api/reports/{i.id}" if i.report_path else None,"detections":[{"class_name":d.class_name,"confidence":d.confidence,"bbox":[d.x1,d.y1,d.x2,d.y2],"area_pixels":d.area_pixels,"severity":d.severity} for d in i.detections]}
@router.post("/auth/register",response_model=Token)
def register(data: Credentials, db: Session=Depends(get_db)):
    if db.query(User).filter_by(email=data.email.lower()).first(): raise HTTPException(409,"Email already registered")
    db.add(User(email=data.email.lower(),password_hash=hash_password(data.password))); db.commit(); return Token(access_token=create_token(data.email.lower()))
@router.post("/auth/login",response_model=Token)
def login(data: Credentials, db: Session=Depends(get_db)):
    u=db.query(User).filter_by(email=data.email.lower()).first()
    if not u or not verify_password(data.password,u.password_hash): raise HTTPException(401,"Incorrect email or password")
    return Token(access_token=create_token(u.email))
@router.get("/auth/me")
def me(user=Depends(user_for)): return {"id":user.id,"email":user.email}
@router.post("/detection/image")
async def image_detection(file: UploadFile=File(...), user=Depends(user_for), db: Session=Depends(get_db)):
    if file.content_type not in IMAGE_TYPES: raise HTTPException(415,"Use JPG, PNG, or WEBP image files")
    payload=await file.read()
    if len(payload)>settings.max_upload_size_mb*1024*1024: raise HTTPException(413,"Upload exceeds configured size limit")
    suffix=Path(file.filename or "image.jpg").suffix.lower(); stem=uuid.uuid4().hex
    source=settings.upload_dir/f"{stem}{suffix}"; source.write_bytes(payload); image=cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None: source.unlink(missing_ok=True); raise HTTPException(422,"Could not read this image")
    detections=detector.infer(image); output=settings.results_dir/f"{stem}.jpg"; ok, encoded=cv2.imencode(".jpg", draw_detections(image,detections)); output.write_bytes(encoded.tobytes())
    highest=next((s for s in ["High","Medium","Low"] if any(d['severity']==s for d in detections)),"None")
    inspection=Inspection(user_id=user.id,filename=file.filename or source.name,input_type="image",total_detections=len(detections),highest_severity=highest,result_path=str(output)); db.add(inspection); db.flush()
    for d in detections: db.add(Detection(inspection_id=inspection.id,class_name=d['class_name'],confidence=d['confidence'],x1=d['bbox'][0],y1=d['bbox'][1],x2=d['bbox'][2],y2=d['bbox'][3],area_pixels=d['area_pixels'],severity=d['severity']))
    db.commit(); db.refresh(inspection); return {**inspection_json(inspection),"model_available":detector.available,"demo_notice":None if detector.available else "No trained road-damage weights are installed. The annotated image is returned with zero detections; add backend/models/road_damage.pt to enable inference."}
@router.post("/detection/live")
async def live(file: UploadFile=File(...), user=Depends(user_for), db: Session=Depends(get_db)): return await image_detection(file,user,db)
@router.post("/detection/video")
async def video_detection(file: UploadFile=File(...), user=Depends(user_for), db: Session=Depends(get_db)):
    if file.content_type not in VIDEO_TYPES: raise HTTPException(415,"Use MP4, AVI, MOV, or MKV video files")
    payload=await file.read()
    if len(payload)>settings.max_upload_size_mb*1024*1024: raise HTTPException(413,"Upload exceeds configured size limit")
    suffix=Path(file.filename or "video.mp4").suffix.lower(); stem=uuid.uuid4().hex; source=settings.upload_dir/f"{stem}{suffix}"; source.write_bytes(payload)
    cap=cv2.VideoCapture(str(source))
    if not cap.isOpened(): raise HTTPException(422,"Could not read this video")
    fps=cap.get(cv2.CAP_PROP_FPS) or 24; width,height=int(cap.get(3)),int(cap.get(4)); output=settings.results_dir/f"{stem}.mp4"; writer=cv2.VideoWriter(str(output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
    count=total=0; confidence_sum=0.; severity={"Low":0,"Medium":0,"High":0}; classes={}; all_found=[]
    while True:
        ok, frame=cap.read()
        if not ok: break
        count+=1; found=detector.infer(frame) if count % settings.process_every_n_frames == 0 else []
        writer.write(draw_detections(frame,found))
        for d in found: total+=1; confidence_sum+=d['confidence']; severity[d['severity']]+=1; classes[d['class_name']]=classes.get(d['class_name'],0)+1; all_found.append(d)
    cap.release(); writer.release(); highest=next((s for s in ["High","Medium","Low"] if severity[s]),"None")
    i=Inspection(user_id=user.id,filename=file.filename or source.name,input_type="video",total_detections=total,highest_severity=highest,result_path=str(output)); db.add(i); db.flush()
    for d in all_found: db.add(Detection(inspection_id=i.id,class_name=d['class_name'],confidence=d['confidence'],x1=d['bbox'][0],y1=d['bbox'][1],x2=d['bbox'][2],y2=d['bbox'][3],area_pixels=d['area_pixels'],severity=d['severity']))
    db.commit(); db.refresh(i)
    return {**inspection_json(i),"frame_count":count,"average_confidence":round(confidence_sum/total,3) if total else 0,"categories":classes,"severity_statistics":severity,"model_available":detector.available,"demo_notice":None if detector.available else "No trained road-damage weights are installed; video was processed without fabricated detections."}
@router.get("/inspections")
def inspections(skip:int=0,limit:int=20,user=Depends(user_for),db:Session=Depends(get_db)):
    items=db.query(Inspection).filter_by(user_id=user.id).order_by(Inspection.created_at.desc()).offset(skip).limit(min(limit,100)).all(); return [inspection_json(i) for i in items]
@router.get("/inspections/{inspection_id}")
def detail(inspection_id:int,user=Depends(user_for),db:Session=Depends(get_db)):
    i=db.query(Inspection).filter_by(id=inspection_id,user_id=user.id).first()
    if not i: raise HTTPException(404,"Inspection not found")
    return inspection_json(i)
@router.delete("/inspections/{inspection_id}",status_code=204)
def delete_inspection(inspection_id:int,user=Depends(user_for),db:Session=Depends(get_db)):
    i=db.query(Inspection).filter_by(id=inspection_id,user_id=user.id).first()
    if not i: raise HTTPException(404,"Inspection not found")
    db.delete(i); db.commit()
@router.get("/reports/{inspection_id}")
def report(inspection_id:int,user=Depends(user_for),db:Session=Depends(get_db)):
    i=db.query(Inspection).filter_by(id=inspection_id,user_id=user.id).first()
    if not i: raise HTTPException(404,"Inspection not found")
    if not i.report_path:
        path=settings.reports_dir/f"inspection-{i.id}.pdf"; generate_report(path,i,i.detections,i.result_path); i.report_path=str(path); db.commit()
    return FileResponse(i.report_path,media_type="application/pdf",filename=f"roadvision-inspection-{i.id}.pdf")
@router.get("/dashboard/statistics")
def statistics(user=Depends(user_for),db:Session=Depends(get_db)):
    q=db.query(Inspection).filter_by(user_id=user.id); inspections=q.all(); ids=[i.id for i in inspections]
    detections=db.query(Detection).filter(Detection.inspection_id.in_(ids)).all() if ids else []
    types={}; severities={"Low":0,"Medium":0,"High":0}
    for d in detections: types[d.class_name]=types.get(d.class_name,0)+1; severities[d.severity]=severities.get(d.severity,0)+1
    return {"total_inspections":len(inspections),"total_damages":len(detections),"potholes":types.get("pothole",0),"cracks":sum(v for k,v in types.items() if "crack" in k),"high_severity":severities["High"],"average_confidence":round(sum(d.confidence for d in detections)/len(detections),3) if detections else 0,"types":types,"severities":severities}
@router.get("/files/results/{name}")
def result_file(name:str):
    path=settings.results_dir/Path(name).name
    if not path.exists(): raise HTTPException(404,"Result not found")
    return FileResponse(path)
