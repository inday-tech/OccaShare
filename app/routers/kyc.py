from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from ..db import database, models
from ..core import security as auth
from ..services.verification import verification_service
import os
import uuid
import shutil

router = APIRouter(prefix="/api/bookings", tags=["kyc"])

UPLOAD_DIR = "app/static/uploads/verification"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/{booking_id}/upload-id")
async def upload_id(
    booking_id: int,
    id_document: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking or (booking.user_id != current_user.id and current_user.role != 'admin'):
        raise HTTPException(status_code=404, detail="Booking not found")

    # Save file
    ext = os.path.splitext(id_document.filename)[1]
    filename = f"booking_{booking_id}_id_{uuid.uuid4()}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(id_document.file, buffer)
    
    id_url = f"/static/uploads/verification/{filename}"

    # Simulate OCR
    result = verification_service.verify_identity(id_url, "pending")
    
    # Log attempt
    attempt = models.VerificationAttempt(
        user_id=current_user.id,
        booking_id=booking_id,
        step="upload",
        status="verified" if result["success"] else "failed",
        details=result["ocr_data"] if result["success"] else {"error": result.get("failure_reason")}
    )
    db.add(attempt)
    
    # Update booking/user
    if result["success"]:
        booking.ocr_verified = True
        # In a real app, we might update user info from OCR here
    
    db.commit()
    return {"success": result["success"], "ocr_data": result.get("ocr_data"), "error": result.get("failure_reason")}

@router.post("/{booking_id}/selfie")
async def upload_selfie(
    booking_id: int,
    selfie: UploadFile = File(...),
    liveness_token: str = Form(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Save file
    ext = os.path.splitext(selfie.filename)[1]
    filename = f"booking_{booking_id}_selfie_{uuid.uuid4()}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(selfie.file, buffer)
    
    selfie_url = f"/static/uploads/verification/{filename}"

    # check liveness
    liveness = verification_service.check_liveness(selfie_url)
    
    attempt = models.VerificationAttempt(
        user_id=current_user.id,
        booking_id=booking_id,
        step="liveness",
        status="verified" if liveness["success"] else "failed",
        details={"liveness_token": liveness.get("liveness_token"), "error": liveness.get("reason")}
    )
    db.add(attempt)
    db.commit()
    
    return {"success": liveness["success"], "liveness_token": liveness.get("liveness_token"), "error": liveness.get("reason")}

@router.get("/{booking_id}/verify")
async def verify_match(
    booking_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # In a real app, you'd pull the latest ID and Selfie URLs from DB/Storage
    # For mock, we'll just assume they've been uploaded
    result = verification_service.verify_identity("id_url", "selfie_url")
    
    attempt = models.VerificationAttempt(
        user_id=current_user.id,
        booking_id=booking_id,
        step="match",
        status="verified" if result["success"] else "failed",
        details={"match_score": 0.95 if result["success"] else 0.4}
    )
    db.add(attempt)
    
    if result["success"]:
        booking.liveness_verified = True
        booking.user.is_kyc_complete = True
        booking.user.is_verified = True
    
    db.commit()
    return {"success": result["success"], "message": "Identity verified" if result["success"] else result.get("failure_reason")}
