
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, time, datetime
from ..db import database, models
from ..core import security as auth
from ..services.verification import verification_service
from ..services.email import EmailService
import shutil
import os
import uuid

router = APIRouter(prefix="/bookings", tags=["bookings"])
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "app/static/uploads/verification"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Helper Functions ---

def get_current_user_from_session(request: Request, db: Session):
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    
    try:
        user = auth.verify_token(token, db)
        return user
    except:
        return None

def save_upload_file(upload_file: UploadFile) -> str:
    file_extension = os.path.splitext(upload_file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
        
    return f"/static/uploads/verification/{unique_filename}"

# --- Wizard Steps ---

# Step 1: Initialize/Select Caterer (from Profile Page)
@router.get("/start/{caterer_id}")
async def start_booking(request: Request, caterer_id: int, package_id: Optional[int] = None, db: Session = Depends(database.get_db)):
    user = get_current_user_from_session(request, db)
    if not user:
        return RedirectResponse(url=f"/auth/login?next=/bookings/start/{caterer_id}")
    
    # NEW: Check if user is already KYC verified? (Optional logic here)
    # Check if user.is_kyc_complete
    
    # Initialize/Reset booking session data
    request.session["booking_data"] = {
        "caterer_id": caterer_id,
        "package_id": package_id,
        "user_id": user.id
    }
    
    # Always go to Phase 1 (Details) now
    return RedirectResponse(url="/bookings/step/details", status_code=303)

# Phase 1: Booking Details (Event Info, Date/Time, Guests)
@router.get("/step/details", response_class=HTMLResponse)
async def step_details_page(request: Request, db: Session = Depends(database.get_db)):
    data = request.session.get("booking_data", {})
    if not data or "caterer_id" not in data:
        return RedirectResponse(url="/customer/marketplace", status_code=303)
    
    package = None
    if data.get("package_id"):
        package = db.query(models.CateringPackage).get(data["package_id"])
    
    caterer = db.query(models.CatererProfile).get(data["caterer_id"])
    
    return templates.TemplateResponse("customer/booking_wizard/step_details.html", {
        "request": request,
        "booking_data": data,
        "package": package,
        "caterer": caterer,
        "current_step": 1
    })

@router.post("/step/details")
async def step_details_submit(
    request: Request,
    caterer_id: int = Form(...),
    package_id: Optional[int] = Form(None),
    event_name: str = Form(...),
    event_type: str = Form(...),
    event_date: date = Form(...),
    event_time: time = Form(...),
    guest_count: int = Form(...),
    venue_address: str = Form(...),
    total_price: float = Form(...),
    reservation_fee: float = Form(...),
    selected_items: list[int] = Form([]),
    selected_addons: list[int] = Form([]),
    special_requests: Optional[str] = Form(""),
    db: Session = Depends(database.get_db)
):
    user = get_current_user_from_session(request, db)
    if not user: return RedirectResponse(url=f"/auth/login?next=/packages/{package_id}")

    # 1. Check Availability
    availability = db.query(models.Availability).filter(
        models.Availability.caterer_id == caterer_id,
        models.Availability.date == event_date,
        models.Availability.is_available == False
    ).first()
    
    if availability:
        return RedirectResponse(url=f"/packages/{package_id}?error=date_unavailable", status_code=303)

    # 2. Create Draft Booking
    new_booking = models.Booking(
        user_id=user.id,
        caterer_id=caterer_id,
        package_id=package_id,
        event_name=event_name,
        event_type=event_type,
        event_date=event_date,
        event_time=event_time,
        venue_address=venue_address,
        guest_count=guest_count,
        total_price=total_price,
        total_amount=total_price, # Sync legacy field
        reservation_fee=reservation_fee,
        special_requests=special_requests,
        status="draft"
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    # 3. Save Selected Items (Base and Add-ons)
    all_items = selected_items + selected_addons
    for item_id in all_items:
        menu_item = db.query(models.MenuItem).get(item_id)
        if menu_item:
            booking_item = models.BookingMenuItem(
                booking_id=new_booking.id,
                menu_item_id=item_id,
                is_add_on=menu_item.is_addon,
                price=menu_item.addon_price if menu_item.is_addon else 0.0
            )
            db.add(booking_item)
    
    db.commit()

    # Update session
    request.session["booking_data"] = {
        "booking_id": new_booking.id,
        "caterer_id": caterer_id,
        "package_id": package_id
    }

    return RedirectResponse(url=f"/bookings/step/kyc/{new_booking.id}", status_code=303)

# Phase 2: Identity Verification
@router.get("/step/kyc/{booking_id}", response_class=HTMLResponse)
async def step_kyc_page(booking_id: int, request: Request, db: Session = Depends(database.get_db)):
    booking = db.query(models.Booking).get(booking_id)
    if not booking: raise HTTPException(status_code=404)
    return templates.TemplateResponse("customer/booking_wizard/step_kyc.html", {
        "request": request,
        "booking_id": booking_id,
        "current_step": 2
    })

# Phase 3: Quotation Review & Contract
@router.get("/step/quotation/{booking_id}", response_class=HTMLResponse)
async def step_quotation_page(booking_id: int, request: Request, db: Session = Depends(database.get_db)):
    booking = db.query(models.Booking).get(booking_id)
    if not booking: raise HTTPException(status_code=404)
    
    # Ensure quotation exists or create one (default 30% downpayment)
    from ..services.quotation import quotation_service
    quotation = quotation_service.get_quotation_by_booking(db, booking_id)
    if not quotation:
        quotation = quotation_service.create_quotation(db, booking, 30)
    
    return templates.TemplateResponse("customer/booking_wizard/step_quotation.html", {
        "request": request,
        "quotation": quotation,
        "current_step": 3
    })

# Phase 4: Downpayment
@router.get("/step/payment/{booking_id}", response_class=HTMLResponse)
async def step_payment_v2_page(booking_id: int, request: Request, db: Session = Depends(database.get_db)):
    booking = db.query(models.Booking).get(booking_id)
    if not booking: raise HTTPException(status_code=404)
    return templates.TemplateResponse("customer/booking_wizard/step_payment.html", {
        "request": request,
        "booking_id": booking_id,
        "booking": booking,
        "current_step": 4
    })

@router.get("/success/{booking_id}", response_class=HTMLResponse)
async def booking_success_page(request: Request, booking_id: int, db: Session = Depends(database.get_db)):
    booking = db.query(models.Booking).get(booking_id)
    return templates.TemplateResponse("customer/booking_success.html", {
        "request": request,
        "booking": booking
    })

@router.post("/review")
async def submit_review(
    request: Request,
    booking_id: int = Form(...),
    rating: int = Form(...),
    comment: str = Form(...),
    recommend: Optional[str] = Form(None),
    ontime: Optional[str] = Form(None),
    db: Session = Depends(database.get_db)
):
    user = get_current_user_from_session(request, db)
    if not user:
        return RedirectResponse(url="/auth/login")

    booking = db.query(models.Booking).get(booking_id)
    if not booking or booking.user_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    new_review = models.Review(
        booking_id=booking_id,
        user_id=user.id,
        caterer_id=booking.caterer_id,
        rating=rating,
        comment=comment,
        recommend=True if recommend else False,
        was_punctual=True if ontime else False
    )
    db.add(new_review)
    
    # Update Caterer Rating
    caterer = booking.caterer
    total_reviews = caterer.review_count + 1
    new_rating = ((caterer.rating * caterer.review_count) + rating) / total_reviews
    caterer.rating = new_rating
    caterer.review_count = total_reviews
    
    # NEW: Mark booking as completed if it wasn't already (optional, usually status should be completed before review)
    # Actually, let's just commit.
    
    db.commit()
    return RedirectResponse(url="/customer/dashboard?success=review_submitted")

# --- KYC API Endpoints (Phase 2 Simulation) ---

@router.post("/{booking_id}/upload-id")
async def upload_id_document(booking_id: int, id_document: UploadFile = File(...), db: Session = Depends(database.get_db)):
    booking = db.query(models.Booking).get(booking_id)
    if not booking:
        return {"success": False, "error": "Booking not found"}
        
    file_url = save_upload_file(id_document)
    
    # Store in OCRVerification
    ocr_verify = db.query(models.OCRVerification).filter(models.OCRVerification.booking_id == booking_id).first()
    if not ocr_verify:
        ocr_verify = models.OCRVerification(booking_id=booking_id, user_id=booking.user_id)
        db.add(ocr_verify)
    
    ocr_verify.document_url = file_url
    ocr_verify.status = "pending"
    db.commit()
    
    return {"success": True, "file_url": file_url}

@router.post("/{booking_id}/selfie")
async def upload_selfie(booking_id: int, selfie: UploadFile = File(...), db: Session = Depends(database.get_db)):
    ocr_verify = db.query(models.OCRVerification).filter(models.OCRVerification.booking_id == booking_id).first()
    if not ocr_verify:
        return {"success": False, "error": "Upload ID first"}
        
    file_url = save_upload_file(selfie)
    ocr_verify.selfie_url = file_url
    db.commit()
    
    return {"success": True, "file_url": file_url}

@router.get("/{booking_id}/api/verify")
async def verify_kyc_api(booking_id: int, db: Session = Depends(database.get_db)):
    booking = db.query(models.Booking).get(booking_id)
    ocr_verify = db.query(models.OCRVerification).filter(models.OCRVerification.booking_id == booking_id).first()
    
    if not ocr_verify or not ocr_verify.document_url or not ocr_verify.selfie_url:
        return {"success": False, "message": "Missing documents for verification"}

    # Simulate OCR & Face Match process
    import time
    time.sleep(1.5) # Simulate processing time
    
    verification_result = verification_service.verify_identity(ocr_verify.document_url, ocr_verify.selfie_url)
    
    if verification_result["success"]:
        ocr_verify.status = "verified"
        ocr_verify.ocr_data = verification_result["ocr_data"]
        ocr_verify.match_score = 0.98 
        
        # Update booking status
        booking.ocr_verified = True
        booking.liveness_verified = True
        
        db.commit()
        return {"success": True, "message": "Identity Verified Successfully"}
    else:
        ocr_verify.status = "failed"
        db.commit()
        return {"success": False, "message": verification_result["failure_reason"]}

@router.post("/{booking_id}/contract/sign")
async def sign_contract(booking_id: int, signature_data: str = Form(...), db: Session = Depends(database.get_db)):
    quotation = db.query(models.Quotation).filter(models.Quotation.booking_id == booking_id).first()
    if not quotation:
        return {"success": False, "error": "Quotation not found"}
        
    quotation.status = "signed"
    # In a real app, we'd save signature_data as an image or a hash
    db.commit()
    
    return {"success": True}
