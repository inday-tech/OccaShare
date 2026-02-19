from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from ..db import database, models
from ..core import security as auth
from ..services.quotation import quotation_service
from typing import Optional
from datetime import datetime

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
    signature_data: str = Form(...), # Base64 or token
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    quotation = db.query(models.Quotation).filter(models.Quotation.booking_id == booking_id).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    quotation.status = "signed"
    # In a real app, generate PDF with signature and store in contract_url
    quotation.contract_url = f"/static/contracts/signed_{booking_id}.pdf"
    
    db.commit()
    return {"success": True, "contract_url": quotation.contract_url}
