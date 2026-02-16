
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, time
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
    # Try getting from session first (if we implemented session auth)
    # OR get from cookie token as per existing implementation
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        scheme, param = token.split() 
        if scheme.lower() != "bearer": 
            return None
        user = auth.verify_token(param, db)
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
    
    # NEW: Check if user is verified
    if not user.is_verified:
        return RedirectResponse(url="/customer/verification?error=verification_required")

    # Clear existing booking session data
    request.session["booking_data"] = {
        "caterer_id": caterer_id,
        "package_id": package_id
    }
    
    # If package is selected, go to Date. Else go to Menu selection.
    if package_id:
        return RedirectResponse(url="/bookings/step/date", status_code=303)
    else:
        return RedirectResponse(url="/bookings/step/menu", status_code=303)

# Step 2 (Optional): Select Menu
@router.get("/step/menu", response_class=HTMLResponse)
async def step_menu_page(request: Request, db: Session = Depends(database.get_db)):
    data = request.session.get("booking_data", {})
    if not data or "caterer_id" not in data:
        return RedirectResponse(url="/caterers")
    
    caterer = db.query(models.CatererProfile).get(data["caterer_id"])
    packages = db.query(models.CateringPackage).filter(models.CateringPackage.caterer_id == caterer.id).all()
    
    return templates.TemplateResponse("customer/booking_wizard/step_menu.html", {
        "request": request,
        "caterer": caterer,
        "packages": packages,
        "current_step": 2
    })

@router.post("/step/menu")
async def step_menu_submit(request: Request, package_id: int = Form(...)):
    data = request.session.get("booking_data", {})
    data["package_id"] = package_id
    request.session["booking_data"] = data
    return RedirectResponse(url="/bookings/step/date", status_code=303)

# Step 3: Date & Time
@router.get("/step/date", response_class=HTMLResponse)
async def step_date_page(request: Request, db: Session = Depends(database.get_db)):
    data = request.session.get("booking_data", {})
    if not data or "caterer_id" not in data:
        return RedirectResponse(url="/caterers")
    
    caterer = db.query(models.CatererProfile).get(data.get("caterer_id"))
    if not caterer:
        return RedirectResponse(url="/caterers")
    
    return templates.TemplateResponse("customer/booking_wizard/step_date.html", {
        "request": request,
        "caterer_id": data["caterer_id"],
        "caterer": caterer,
        "current_step": 3
    })

@router.post("/step/date")
async def step_date_submit(
    request: Request, 
    event_date: date = Form(...), 
    event_time: time = Form(...),
    guest_count: int = Form(...),
    special_requests: Optional[str] = Form(""),
    db: Session = Depends(database.get_db)
):
    if event_date < date.today():
         return RedirectResponse(url="/bookings/step/date?error=past_date")

    data = request.session.get("booking_data", {})
    caterer_id = data.get("caterer_id")
    
    # NEW: Check availability
    availability = db.query(models.Availability).filter(
        models.Availability.caterer_id == caterer_id,
        models.Availability.date == event_date,
        models.Availability.is_available == False
    ).first()
    
    if availability:
        return RedirectResponse(url="/bookings/step/date?error=date_unavailable")

    data.update({
        "event_date": str(event_date),
        "event_time": str(event_time),
        "guest_count": guest_count,
        "special_requests": special_requests
    })
    request.session["booking_data"] = data
    return RedirectResponse(url="/bookings/step/details", status_code=303)

# Step 4: Booking Details
@router.get("/step/details", response_class=HTMLResponse)
async def step_details_page(request: Request, db: Session = Depends(database.get_db)):
    data = request.session.get("booking_data", {})
    if not data:
        return RedirectResponse(url="/caterers")
    
    return templates.TemplateResponse("customer/booking_wizard/step_details.html", {
        "request": request,
        "booking_data": data,
        "current_step": 4
    })

@router.post("/step/details")
async def step_details_submit(
    request: Request,
    event_name: str = Form(...),
    event_type: str = Form(...),
    venue_address: str = Form(...),
    special_requests: Optional[str] = Form("")
):
    data = request.session.get("booking_data", {})
    data.update({
        "event_name": event_name,
        "event_type": event_type,
        "venue_address": venue_address,
        "special_requests": special_requests
    })
    request.session["booking_data"] = data
    return RedirectResponse(url="/bookings/step/review", status_code=303)

# Step 4: Review
@router.get("/step/review", response_class=HTMLResponse)
async def step_review_page(request: Request, db: Session = Depends(database.get_db)):
    data = request.session.get("booking_data", {})
    if not data:
        return RedirectResponse(url="/caterers")
    
    caterer = db.query(models.CatererProfile).get(data.get("caterer_id"))
    package = db.query(models.CateringPackage).get(data.get("package_id")) if data.get("package_id") else None
    
    # Calculate price
    total_price = 0
    if package:
        if package.price_unit == 'per_guest':
            total_price = package.price * int(data.get("guest_count", 0))
        else:
            total_price = package.price
    
    data["total_price"] = total_price
    request.session["booking_data"] = data

    return templates.TemplateResponse("customer/booking_wizard/step_review.html", {
        "request": request,
        "data": data,
        "caterer": caterer,
        "package": package,
        "total_price": total_price,
        "current_step": 5,
        "next_url": "/bookings/step/verify"
    })

# Step 5: Verify (Mandatory)
@router.get("/step/verify", response_class=HTMLResponse)
async def step_verify_page(request: Request):
    return templates.TemplateResponse("customer/booking_wizard/step_verify.html", {
        "request": request,
        "current_step": 6
    })

from ..services.verification import verification_service
import shutil
import os

@router.post("/step/verify")
async def step_verify_submit(
    request: Request,
    id_document: UploadFile = File(...),
    selfie: UploadFile = File(...)
):
    data = request.session.get("booking_data", {})
    if not data:
        return RedirectResponse(url="/caterers")

    # Save files temporarily (Mocking storage)
    os.makedirs("app/static/verification", exist_ok=True)
    id_path = f"app/static/verification/id_{request.session.get('user_id')}_{int(time.time())}.jpg"
    selfie_path = f"app/static/verification/selfie_{request.session.get('user_id')}_{int(time.time())}.jpg"
    
    with open(id_path, "wb") as buffer:
        shutil.copyfileobj(id_document.file, buffer)
    with open(selfie_path, "wb") as buffer:
        shutil.copyfileobj(selfie.file, buffer)

    # Call Verification Service
    result = verification_service.verify_identity(id_path, selfie_path)
    
    if not result["success"]:
        # If verification failed, stay on page with error
        return templates.TemplateResponse("customer/booking_wizard/step_verify.html", {
            "request": request,
            "error": result["failure_reason"],
            "current_step": 6
        })

    # Store verification results
    data["verification"] = {
        "verified": True,
        "doc_url": id_path,
        "selfie_url": selfie_path,
        "ocr_data": result["ocr_data"]
    }
    request.session["booking_data"] = data
    
    return RedirectResponse(url="/bookings/step/payment", status_code=303)

# Step 7: Payment
@router.get("/step/payment", response_class=HTMLResponse)
async def step_payment_page(request: Request):
    data = request.session.get("booking_data", {})
    if not data:
        return RedirectResponse(url="/caterers")
    return templates.TemplateResponse("customer/booking_wizard/step_payment.html", {
        "request": request,
        "current_step": 7
    })

import asyncio

@router.post("/step/payment")
async def step_payment_submit(request: Request, payment_method: str = Form(...)):
    data = request.session.get("booking_data", {})
    data["payment_method"] = payment_method
    
    # NEW: Simulate Payment Processing (Non-blocking)
    await asyncio.sleep(1.5) 
    
    request.session["booking_data"] = data
    return RedirectResponse(url="/bookings/confirm", status_code=303)

# Step 8: Confirmation / Create Booking
@router.get("/confirm")
async def confirm_booking_process(request: Request, db: Session = Depends(database.get_db)):
    # In a stricter REST verification, this would be a POST from review or verify step.
    # But since we are redirecting, we'll handle the creation here.
    
    data = request.session.get("booking_data")
    if not data:
        return RedirectResponse(url="/caterers")
    
    user = get_current_user_from_session(request, db)
    if not user:
        return RedirectResponse(url=f"/auth/login?next=/bookings/confirm")

    # Mandatory Identity Verification Check
    ver_data = data.get("verification")
    if not ver_data or not ver_data.get("verified"):
        return RedirectResponse(url="/bookings/step/verify?error=verification_required")

    # Payment method check
    if "payment_method" not in data:
        return RedirectResponse(url="/bookings/step/payment")

    from datetime import datetime

    # Create Booking
    new_booking = models.Booking(
        user_id=user.id,
        caterer_id=data["caterer_id"],
        package_id=data["package_id"],
        event_name=data.get("event_name"),
        event_type=data.get("event_type"),
        event_date=datetime.strptime(data["event_date"], '%Y-%m-%d').date(),
        event_time=datetime.strptime(data["event_time"], '%H:%M').time() if data.get("event_time") else None,
        venue_address=data.get("venue_address"),
        guest_count=data["guest_count"],
        total_amount=data["total_price"],
        special_requests=data.get("special_requests"),
        status="pending",
        payment_status="pending",
        payment_method=data.get("payment_method", "TBD"),
        ocr_verified=data.get("verification", {}).get("verified", False),
        liveness_verified=data.get("verification", {}).get("verified", False)
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    
    # History Log
    history = models.BookingHistory(
        booking_id=new_booking.id,
        status="pending",
        notes="Booking created via wizard"
    )
    db.add(history)
    
    # OCR Record
    ver_data = data.get("verification")
    if ver_data:
        ocr_rec = models.OCRVerification(
            booking_id=new_booking.id,
            user_id=user.id,
            document_url=ver_data["doc_url"],
            selfie_url=ver_data["selfie_url"],
            status="verified" if ver_data["verified"] else "failed",
            ocr_data=ver_data["ocr_data"]
        )
        db.add(ocr_rec)
        
    db.commit()
    
    # Clear session
    request.session.pop("booking_data", None)
    
    return RedirectResponse(url=f"/bookings/success/{new_booking.id}", status_code=303)

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
