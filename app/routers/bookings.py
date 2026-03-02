
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

@router.get("/my")
async def my_bookings_redirect():
    return RedirectResponse(url="/customer/bookings", status_code=303)

# --- Wizard Steps ---

# Step 1: Initialize/Select Caterer (from Profile Page)
@router.get("/start/{caterer_id}")
async def start_booking(request: Request, caterer_id: int, package_id: Optional[int] = None, db: Session = Depends(database.get_db)):
    user = get_current_user_from_session(request, db)
    if not user:
        return RedirectResponse(url=f"/auth/login?next=/bookings/start/{caterer_id}")
    
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

@router.get("/continue/{booking_id}")
async def continue_draft_booking(booking_id: int, request: Request, db: Session = Depends(database.get_db)):
    user = get_current_user_from_session(request, db)
    if not user:
        return RedirectResponse(url=f"/auth/login?next=/bookings/continue/{booking_id}")
        
    booking = db.query(models.Booking).get(booking_id)
    if not booking or booking.user_id != user.id:
        return RedirectResponse(url="/customer/dashboard?error=booking_not_found", status_code=303)
        
    if booking.status != 'draft':
        return RedirectResponse(url=f"/customer/bookings/manage/{booking.id}", status_code=303)
        
    # Re-populate session so back-navigation works
    request.session["booking_data"] = {
        "booking_id": booking.id,
        "caterer_id": booking.caterer_id,
        "package_id": booking.package_id,
        "user_id": user.id
    }
    
    # Step logic routing
    # 1. Does user need KYC?
    if not user.is_verified and not user.is_kyc_complete:
        return RedirectResponse(url=f"/bookings/step/kyc/{booking.id}", status_code=303)
        
    # 2. Is there a Quotation yet?
    if not booking.quotation:
        # User hasn't finished quotation step
        return RedirectResponse(url=f"/bookings/step/quotation/{booking.id}", status_code=303)
        
    # 3. Has the Quotation been signed?
    if booking.quotation.status == 'signed':
        return RedirectResponse(url=f"/bookings/step/payment/{booking.id}", status_code=303)
        
    # Default fallback to Quotation
    return RedirectResponse(url=f"/bookings/step/quotation/{booking.id}", status_code=303)

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
        "booking": booking,
        "package": booking.package,
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

@router.post("/step/payment/{path_booking_id}")
@router.post("/step/payment")
async def step_payment_submit(
    request: Request,
    path_booking_id: Optional[int] = None, # Matches URL path if present
    db: Session = Depends(database.get_db)
):
    # Support URL path variable or Form body
    try:
        form_data = await request.form()
        booking_id_str = form_data.get("booking_id")
        booking_id = int(booking_id_str) if booking_id_str else None
        payment_method = form_data.get("payment_method", "GCash")
    except Exception:
        booking_id = None
        payment_method = "GCash"
        
    actual_booking_id = path_booking_id or booking_id
    
    if not actual_booking_id:
        # Emergency fallback: Try to get from session if all else fails
        session_data = request.session.get("booking_data", {})
        actual_booking_id = session_data.get("id")
        
    if not actual_booking_id:
        raise HTTPException(status_code=400, detail="Booking ID is missing from request")

    booking = db.query(models.Booking).get(actual_booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Handle Cash Payment
    if payment_method == "Cash":
        booking.payment_method = "Cash"
        booking.payment_status = "pending" # Paid upon physical meeting or specific caterer terms
        booking.status = "pending"       # Now waiting for caterer to accept
        
        # Save to history
        history = models.BookingHistory(
            booking_id=booking.id,
            status="pending",
            notes=f"Reservation requested with Cash Payment. Transaction to be settled per caterer's terms."
        )
        db.add(history)
        db.commit()
        return RedirectResponse(url=f"/bookings/success/{booking.id}", status_code=303)

    import os
    import httpx
    
    paymongo_secret = os.getenv("PAYMONGO_SECRET_KEY")
    if paymongo_secret:
        # Generate Paymongo Checkout Link
        url = "https://api.paymongo.com/v1/links"
        amount_cents = int((booking.reservation_fee or 0) * 100)
        
        # Paymongo requires at least 100 PHP (10000 cents) usually, but we assume reservation_fee is valid
        if amount_cents >= 10000:
            base_url = os.getenv("SITE_URL", "http://localhost:8000")
            payload = {
                "data": {
                    "attributes": {
                        "amount": amount_cents,
                        "description": f"Reservation Fee for Booking #{booking.id}",
                        "remarks": f"booking_id:{booking.id}",
                        "redirect": {
                            "success": f"{base_url}/bookings/my?payment=success",
                            "failed": f"{base_url}/bookings/my?payment=failed"
                        }
                    }
                }
            }
            
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(url, json=payload, auth=(paymongo_secret, ""))
                    if response.status_code == 200:
                        data = response.json()
                        checkout_url = data["data"]["attributes"]["checkout_url"]
                        reference_number = data["data"]["attributes"]["reference_number"]
                        
                        booking.payment_method = payment_method
                        booking.status = "pending_payment" # Wait for webhook
                        
                        history = models.BookingHistory(
                            booking_id=booking.id,
                            status="pending_payment",
                            notes=f"Redirected to Paymongo ({reference_number})"
                        )
                        db.add(history)
                        db.commit()
                        
                        return RedirectResponse(url=checkout_url, status_code=303)
                    else:
                        print("Paymongo API Error:", response.text)
                except Exception as e:
                    print("Paymongo Request Error:", str(e))

    # Simulate payment processing (Fallback for other methods)
    booking.payment_method = payment_method
    booking.payment_status = "paid"  # Simulating successful payment
    booking.status = "pending"       # Now waiting for caterer to accept
    
    # Save to history
    history = models.BookingHistory(
        booking_id=booking.id,
        status="pending",
        notes=f"Payment of reservation fee completed via {payment_method}. (Simulated)"
    )
    db.add(history)
    db.commit()

    return RedirectResponse(url=f"/bookings/success/{booking.id}", status_code=303)

@router.post("/pay-balance/{booking_id}")
async def pay_balance_submit(
    booking_id: int,
    request: Request,
    payment_method: str = Form("Paymongo"),
    db: Session = Depends(database.get_db)
):
    user = get_current_user_from_session(request, db)
    if not user: raise HTTPException(status_code=401)
    
    booking = db.query(models.Booking).get(booking_id)
    if not booking or booking.user_id != user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    if booking.status != 'confirmed':
        raise HTTPException(status_code=400, detail="Only confirmed bookings can have balances paid.")

    outstanding_balance = float(booking.total_amount or 0) - float(booking.reservation_fee or 0)
    
    if outstanding_balance <= 0:
        return RedirectResponse(url=f"/customer/bookings/manage/{booking.id}?info=balance_zero", status_code=303)

    # Handle Cash Payment for Balance
    if payment_method == "Cash":
        # Keep status as confirmed, but perhaps add a note
        history = models.BookingHistory(
            booking_id=booking.id,
            status="confirmed",
            notes=f"Outstanding balance of ₱{outstanding_balance:,.2f} marked for Cash Payment."
        )
        db.add(history)
        db.commit()
        return RedirectResponse(url=f"/customer/bookings/manage/{booking.id}?success=payment_marked_cash", status_code=303)

    import os
    import httpx
    
    paymongo_secret = os.getenv("PAYMONGO_SECRET_KEY")
    if paymongo_secret:
        url = "https://api.paymongo.com/v1/links"
        amount_cents = int(outstanding_balance * 100)
        
        if amount_cents >= 10000:
            base_url = os.getenv("SITE_URL", "http://localhost:8000")
            payload = {
                "data": {
                    "attributes": {
                        "amount": amount_cents,
                        "description": f"Outstanding Balance for Booking #{booking.id}",
                        "remarks": f"booking_id:{booking.id}_balance",
                        "redirect": {
                            "success": f"{base_url}/customer/bookings/manage/{booking.id}?payment=success",
                            "failed": f"{base_url}/customer/bookings/manage/{booking.id}?payment=failed"
                        }
                    }
                }
            }
            
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(url, json=payload, auth=(paymongo_secret, ""))
                    if response.status_code == 200:
                        data = response.json()
                        checkout_url = data["data"]["attributes"]["checkout_url"]
                        
                        history = models.BookingHistory(
                            booking_id=booking.id,
                            status="confirmed",
                            notes=f"Redirected to Paymongo for balance payment (₱{outstanding_balance:,.2f})"
                        )
                        db.add(history)
                        db.commit()
                        return RedirectResponse(url=checkout_url, status_code=303)
                except Exception as e:
                    print("Paymongo Balance Payment Error:", str(e))

    # Fallback/Simulation
    booking.payment_status = "paid"
    history = models.BookingHistory(
        booking_id=booking.id,
        status="confirmed",
        notes=f"Outstanding balance of ₱{outstanding_balance:,.2f} successfully paid via {payment_method}. (Simulated)"
    )
    db.add(history)
    db.commit()

    return RedirectResponse(url=f"/customer/bookings/manage/{booking.id}?success=balance_paid", status_code=303)

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
    return RedirectResponse(url="/customer/dashboard?success=review_submitted", status_code=303)


# Note: Contract signing logic has been moved to quotations.py router.
