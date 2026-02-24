
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
    
    # If no package selected, go to Menu Selection first
    if not package_id:
        return RedirectResponse(url=f"/bookings/step/menu/{caterer_id}", status_code=303)
    
    # Always go to Phase 1 (Details) if package is already selected
    return RedirectResponse(url="/bookings/step/details", status_code=303)

# New: Package Selection Step (If not selected from Marketplace)
@router.get("/step/menu/{caterer_id}", response_class=HTMLResponse)
async def step_menu_page(caterer_id: int, request: Request, db: Session = Depends(database.get_db)):
    caterer = db.query(models.CatererProfile).get(caterer_id)
    if not caterer: raise HTTPException(status_code=404)
    
    packages = db.query(models.CateringPackage).filter(models.CateringPackage.caterer_id == caterer_id).all()
    user = get_current_user_from_session(request, db)
    
    return templates.TemplateResponse("customer/booking_wizard/step_menu.html", {
        "request": request,
        "caterer": caterer,
        "packages": packages,
        "user": user,
        "current_step": 0, # Step 0 for menu selection if needed
        "active_page": "bookings"
    })

@router.post("/step/menu")
async def step_menu_submit(request: Request, package_id: int = Form(...)):
    data = request.session.get("booking_data", {})
    data["package_id"] = package_id
    request.session["booking_data"] = data
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
    
    user = get_current_user_from_session(request, db)
    return templates.TemplateResponse("customer/booking_wizard/step_details.html", {
        "request": request,
        "booking_data": data,
        "package": package,
        "caterer": caterer,
        "user": user,
        "current_step": 1,
        "active_page": "bookings"
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
    user = get_current_user_from_session(request, db)
    return templates.TemplateResponse("customer/booking_wizard/step_kyc.html", {
        "request": request,
        "booking_id": booking_id,
        "user": user,
        "current_step": 2,
        "active_page": "bookings"
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
    
    user = get_current_user_from_session(request, db)
    return templates.TemplateResponse("customer/booking_wizard/step_quotation.html", {
        "request": request,
        "quotation": quotation,
        "user": user,
        "current_step": 3,
        "active_page": "bookings"
    })

# Phase 4: Downpayment
@router.get("/step/payment/{booking_id}", response_class=HTMLResponse)
async def step_payment_v2_page(booking_id: int, request: Request, db: Session = Depends(database.get_db)):
    booking = db.query(models.Booking).get(booking_id)
    if not booking: raise HTTPException(status_code=404)
    user = get_current_user_from_session(request, db)
    return templates.TemplateResponse("customer/booking_wizard/step_payment.html", {
        "request": request,
        "booking_id": booking_id,
        "booking": booking,
        "user": user,
        "current_step": 4,
        "active_page": "bookings"
    })

@router.post("/step/payment/{booking_id}")
async def step_payment_submit(
    booking_id: int,
    request: Request,
    payment_method: str = Form(...),
    db: Session = Depends(database.get_db)
):
    booking = db.query(models.Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Simulate payment processing
    # In a real app, this would redirect to a payment gateway or handle response
    booking.payment_method = payment_method
    booking.payment_status = "paid"  # Simulating successful payment
    booking.status = "pending"       # Now waiting for caterer to accept
    
    # Save to history
    history = models.BookingHistory(
        booking_id=booking.id,
        status="pending",
        notes=f"Payment of reservation fee completed via {payment_method}. Booking is now pending caterer approval."
    )
    db.add(history)
    db.commit()

    return RedirectResponse(url=f"/bookings/success/{booking.id}", status_code=303)

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

@router.post("/{booking_id}/contract/sign")
async def sign_contract(booking_id: int, signature_data: str = Form(...), db: Session = Depends(database.get_db)):
    quotation = db.query(models.Quotation).filter(models.Quotation.booking_id == booking_id).first()
    if not quotation:
        return {"success": False, "error": "Quotation not found"}
        
    quotation.status = "signed"
    # In a real app, we'd save signature_data as an image or a hash
    db.commit()
    
    return {"success": True}
