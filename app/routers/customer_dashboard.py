from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, UploadFile, File
from typing import Optional
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date
import os
import shutil
import uuid
from ..db import database, models
from ..core import security as auth

router = APIRouter(prefix="/customer", tags=["customer"])
templates = Jinja2Templates(directory="templates")

# Standard dependency for customer access
customer_only = auth.RoleChecker(["customer"])

@router.get("/dashboard", response_class=HTMLResponse)
async def customer_dashboard(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    bookings = user.bookings
    today = date.today()
    upcoming_count = 0
    
    # Calculate upcoming count safely
    for b in bookings:
        if b.event_date and b.status != 'cancelled':
            try:
                b_date = b.event_date.date() if hasattr(b.event_date, 'date') else b.event_date
                if b_date >= today:
                    upcoming_count += 1
            except:
                continue

    # Create display-friendly booking list
    display_bookings = []
    for b in bookings[:5]:
        b_data = {
            "id": b.id,
            "event_name": b.event_name or "Event Name",
            "caterer_name": b.caterer.business_name if b.caterer else "Unknown Caterer",
            "status": b.status or "pending",
            "payment_status": b.payment_status or "pending",
            "payment_method": b.payment_method or "Method TBD",
            "has_review": b.review is not None
        }
        
        # Safe Date Formatting
        try:
            if b.event_date:
                b_data["display_date"] = b.event_date.strftime('%B %d, %Y')
            else:
                b_data["display_date"] = "Date TBD"
        except:
            b_data["display_date"] = str(b.event_date) if b.event_date else "Date TBD"
            
        # Safe Time Formatting
        try:
            if b.event_time:
                b_data["display_time"] = b.event_time.strftime('%I:%M %p')
            else:
                b_data["display_time"] = "Time TBD"
        except:
            b_data["display_time"] = str(b.event_time) if b.event_time else "Time TBD"
            
        # Safe Amount Formatting
        try:
            if b.total_amount is not None:
                amount = float(b.total_amount)
                b_data["display_amount"] = f"₱{amount:,.2f}"
            else:
                b_data["display_amount"] = "₱0.00"
        except:
            b_data["display_amount"] = f"₱{b.total_amount or '0.00'}"
            
        display_bookings.append(b_data)

    return templates.TemplateResponse("customer/dashboard.html", {
        "request": request,
        "user": user,
        "bookings": display_bookings,
        "total_count": len(bookings),
        "upcoming_count": upcoming_count,
        "active_page": "overview",
        "client_id": f"dashboard_{user.id}"
    })

@router.get("/feedback/{booking_id}", response_class=HTMLResponse)
async def feedback_page(
    request: Request,
    booking_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    booking = db.query(models.Booking).get(booking_id)
    if not booking or booking.user_id != user.id:
        return RedirectResponse(url="/customer/dashboard?error=not_found")
    
    if booking.status != 'completed':
        return RedirectResponse(url="/customer/dashboard?error=not_completed")
        
    if booking.review:
        return RedirectResponse(url="/customer/dashboard?error=already_reviewed")

    return templates.TemplateResponse("customer/feedback.html", {
        "request": request,
        "user": user,
        "booking": booking
    })

@router.get("/bookings", response_class=HTMLResponse)
async def customer_bookings(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    return templates.TemplateResponse("customer/bookings.html", {
        "request": request,
        "user": user,
        "bookings": user.bookings,
        "active_page": "bookings"
    })

@router.get("/payments", response_class=HTMLResponse)
async def customer_payments(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    bookings = user.bookings
    return templates.TemplateResponse("customer/payments.html", {
        "request": request,
        "user": user,
        "bookings": bookings,
        "active_page": "payments"
    })

@router.get("/reviews", response_class=HTMLResponse)
async def customer_reviews(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    return templates.TemplateResponse("customer/reviews.html", {
        "request": request,
        "user": user,
        "reviews": user.reviews,
        "active_page": "reviews"
    })

@router.get("/profile", response_class=HTMLResponse)
async def customer_profile(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    return templates.TemplateResponse("customer/profile.html", {
        "request": request,
        "user": user,
        "active_page": "profile"
    })

@router.get("/promotions", response_class=HTMLResponse)
async def customer_promotions(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    promotions = db.query(models.Promotion).filter(models.Promotion.is_active == True).all()
    return templates.TemplateResponse("customer/promotions.html", {
        "request": request, 
        "user": user,
        "promotions": promotions,
        "active_page": "promotions"
    })

@router.get("/marketplace", response_class=HTMLResponse)
async def customer_marketplace(
    request: Request,
    q: Optional[str] = None,
    event_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    rating: Optional[float] = None,
    city: Optional[str] = None,
    sort: Optional[str] = "newest",
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    query = db.query(models.CatererProfile).filter(models.CatererProfile.verification_status == "Verified")

    if q:
        query = query.filter(
            (models.CatererProfile.business_name.ilike(f"%{q}%")) |
            (models.CatererProfile.description.ilike(f"%{q}%"))
        )
    
    if event_type:
        query = query.filter(models.CatererProfile.business_type == event_type)
    
    if rating:
        query = query.filter(models.CatererProfile.rating >= rating)
    
    if city:
        query = query.filter(models.CatererProfile.city == city)

    # Note: Filtering by package price requires a join
    if min_price is not None or max_price is not None:
        query = query.join(models.CateringPackage)
        if min_price is not None:
            query = query.filter(models.CateringPackage.price >= min_price)
        if max_price is not None:
            query = query.filter(models.CateringPackage.price <= max_price)
        query = query.distinct()

    if sort == "rating":
        query = query.order_by(models.CatererProfile.rating.desc())
    elif sort == "price_low":
        # Simplified sort by first package price
        query = query.join(models.CateringPackage).order_by(models.CateringPackage.price.asc())
    else:
        query = query.order_by(models.CatererProfile.created_at.desc())

    caterers = query.all()
    
    # Get unique cities and types for filters
    cities = db.query(models.CatererProfile.city).distinct().all()
    types = db.query(models.CatererProfile.business_type).distinct().all()

    return templates.TemplateResponse("customer/marketplace.html", {
        "request": request,
        "user": user,
        "caterers": caterers,
        "cities": [c[0] for c in cities if c[0]],
        "types": [t[0] for t in types if t[0]],
        "active_page": "marketplace",
        "current_step": 1,
        "filters": {
            "q": q,
            "event_type": event_type,
            "min_price": min_price,
            "max_price": max_price,
            "rating": rating,
            "city": city,
            "sort": sort
        }
    })

@router.post("/profile/update")
async def update_profile(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone_number: Optional[str] = Form(None),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    user.first_name = first_name
    user.last_name = last_name
    user.phone_number = phone_number
    db.commit()
    return RedirectResponse(url="/customer/profile?success=profile_updated", status_code=303)

@router.post("/profile/photo")
async def update_profile_photo(
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    UPLOAD_DIR = "app/static/uploads/profiles"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    user.profile_image_url = f"/static/uploads/profiles/{filename}"
    db.commit()
    
    return RedirectResponse(url="/customer/profile?success=photo_updated", status_code=303)
