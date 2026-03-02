from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from sqlalchemy.orm import Session
from ..db import database, models
from ..core import security as auth
from ..services.quotation import quotation_service
from typing import Optional
from datetime import datetime
from sqlalchemy import func

router = APIRouter(prefix="/api/bookings", tags=["quotations"])

@router.post("/quote")
async def create_quote_request(
    caterer_id: int = Form(...),
    package_id: int = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    guest_count: int = Form(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # check availability
    date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
    availability = db.query(models.Availability).filter(
        models.Availability.caterer_id == caterer_id,
        models.Availability.date == date_obj,
        models.Availability.is_available == False
    ).first()
    
    if availability:
        raise HTTPException(status_code=400, detail="Date is unavailable")

    package = db.query(models.CateringPackage).get(package_id)
    if not package:
         raise HTTPException(status_code=404, detail="Package not found")

    # Create draft booking
    booking = models.Booking(
        user_id=current_user.id,
        caterer_id=caterer_id,
        package_id=package_id,
        event_date=date_obj,
        event_time=datetime.strptime(event_time, '%H:%M').time(),
        guest_count=guest_count,
        status="draft",
        total_amount=0 # will be set by quotation
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    
    return {"booking_id": booking.id}

@router.get("/{booking_id}")
async def get_booking(
    booking_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    booking = db.query(models.Booking).get(booking_id)
    if not booking or (booking.user_id != current_user.id and current_user.role != 'admin'):
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return booking

@router.post("/{booking_id}/calculate")
async def calculate_quotation(
    booking_id: int,
    request: Request,
    guest_count: int = Form(...),
    downpayment_percent: int = Form(...),
    db: Session = Depends(database.get_db),
):
    # Session-based auth (same as booking wizard pages)
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if token.startswith("Bearer "):
        token = token.split(" ", 1)[1]
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Not authenticated")
        current_user = db.query(models.User).filter(models.User.email == email).first()
        if not current_user:
            raise HTTPException(status_code=401, detail="Not authenticated")
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    booking = db.query(models.Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    package = booking.package
    from decimal import Decimal
    
    # Calculate base amount
    actual_unit_price = package.price_per_head if hasattr(package, 'price_per_head') and package.price_per_head else package.price
    unit_price = Decimal(str(actual_unit_price))
    base_amount = unit_price * Decimal(str(guest_count))
    
    # Calculate addon total
    from ..db.models import BookingMenuItem
    addon_total = db.query(func.sum(BookingMenuItem.price)).filter(
        BookingMenuItem.booking_id == booking_id,
        BookingMenuItem.is_add_on == True
    ).scalar() or 0.0
    
    total_amount = base_amount + Decimal(str(addon_total))
    deposit_amount = total_amount * (Decimal(str(downpayment_percent)) / Decimal("100"))
    
    return {
        "success": True,
        "base_amount": float(base_amount),
        "total_amount": float(total_amount),
        "deposit_amount": float(deposit_amount),
        "guest_count": guest_count,
        "downpayment_percent": downpayment_percent,
        "unit_price": float(unit_price)
    }

@router.post("/{booking_id}/quotation")
async def generate_quotation(
    booking_id: int,
    downpayment_percent: int = Form(30),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    booking = db.query(models.Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    try:
        quotation = quotation_service.create_quotation(db, booking, downpayment_percent)
        return quotation
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{booking_id}/contract/sign")
async def sign_contract(
    booking_id: int,
    signature_data: str = Form(...),
    guest_count: Optional[int] = Form(None),
    downpayment_percent: Optional[int] = Form(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    quotation = db.query(models.Quotation).filter(models.Quotation.booking_id == booking_id).first()
    booking = db.query(models.Booking).get(booking_id)
    
    if not quotation or not booking:
        raise HTTPException(status_code=404, detail="Quotation or Booking not found")

    # Update Downpayment Percentage
    if downpayment_percent:
        quotation.downpayment_percent = int(downpayment_percent)
        
    from decimal import Decimal
    dp_factor = Decimal(str(quotation.downpayment_percent / 100))
    
    # Sync guest count if adjusted
    if guest_count and guest_count != quotation.package_details.get("guest_count"):
        unit_price = Decimal(str(quotation.package_details.get("unit_price", 0)))
        new_guest_count = int(guest_count)
        new_base_amount = unit_price * new_guest_count
        
        addon_total = sum(Decimal(str(a.get("price", 0))) for a in quotation.addons)
        new_total = new_base_amount + addon_total
        
        details = quotation.package_details.copy()
        details["guest_count"] = new_guest_count
        details["base_amount"] = float(new_base_amount)
        quotation.package_details = details
        quotation.total_amount = float(new_total)
        
        booking.guest_count = new_guest_count
        booking.total_amount = float(new_total)
        booking.reservation_fee = new_total * dp_factor
    else:
        new_total = Decimal(str(quotation.total_amount))
        booking.reservation_fee = new_total * dp_factor

    quotation.status = "signed"
    # signature_data can be stored in a signature field if added to model later
    
    db.commit()
    return {"success": True}
