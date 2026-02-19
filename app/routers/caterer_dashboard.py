from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, UploadFile, File
from typing import Optional
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..db import database, models, schemas
from ..core import security as auth
import os
import shutil
import uuid

router = APIRouter(prefix="/caterer", tags=["caterer"])
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "app/static/uploads/caterer"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Standard dependency for caterer access
caterer_only = auth.RoleChecker(["caterer"])

@router.get("/dashboard", response_class=HTMLResponse)
async def caterer_dashboard(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    profile = user.caterer_profile
    bookings = profile.bookings
    
    # Calculate Stats
    total_revenue = sum(b.total_amount for b in bookings if b.payment_status in ['paid', 'deposit_paid'])
    active_bookings = sum(1 for b in bookings if b.status in ['pending', 'confirmed'])
    
    return templates.TemplateResponse("caterer/index.html", {
        "request": request,
        "user": user,
        "profile": profile,
        "bookings": bookings[:5], # Recent 5 bookings
        "total_revenue": total_revenue,
        "active_bookings_count": active_bookings,
        "total_bookings_count": len(bookings),
        "active_page": "overview"
    })

@router.get("/bookings", response_class=HTMLResponse)
async def manage_bookings(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    return templates.TemplateResponse("caterer/bookings.html", {
        "request": request,
        "user": user,
        "bookings": user.caterer_profile.bookings,
        "active_page": "bookings"
    })

@router.get("/payments", response_class=HTMLResponse)
async def caterer_payments(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    return templates.TemplateResponse("caterer/payments.html", {
        "request": request,
        "user": user,
        "bookings": user.caterer_profile.bookings,
        "active_page": "payments"
    })

@router.get("/reviews", response_class=HTMLResponse)
async def caterer_reviews(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    return templates.TemplateResponse("caterer/reviews.html", {
        "request": request,
        "user": user,
        "reviews": user.caterer_profile.reviews,
        "active_page": "reviews"
    })

@router.get("/customers", response_class=HTMLResponse)
async def caterer_customers(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    # Get unique customers and their stats
    customer_ids = {b.user_id for b in user.caterer_profile.bookings}
    customers = []
    if customer_ids:
        raw_customers = db.query(models.User).filter(models.User.id.in_(customer_ids)).all()
        for c in raw_customers:
            # Stats for this customer relative to THIS caterer
            bookings_count = db.query(models.Booking).filter(
                models.Booking.user_id == c.id,
                models.Booking.caterer_id == user.caterer_profile.id
            ).count()
            
            avg_rating = db.query(func.avg(models.Review.rating)).filter(
                models.Review.user_id == c.id,
                models.Review.caterer_id == user.caterer_profile.id
            ).scalar() or 0
            
            # Attach custom attributes for template
            c.total_bookings = bookings_count
            c.avg_rating = round(float(avg_rating), 1)
            customers.append(c)
    
    return templates.TemplateResponse("caterer/customers.html", {
        "request": request,
        "user": user,
        "customers": customers,
        "active_page": "customers"
    })

@router.get("/calendar", response_class=HTMLResponse)
async def caterer_calendar(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    # For the list view on the side
    confirmed_bookings = db.query(models.Booking).filter(
        models.Booking.caterer_id == user.caterer_profile.id,
        models.Booking.status == 'confirmed'
    ).order_by(models.Booking.event_date).all()
    
    return templates.TemplateResponse("caterer/calendar.html", {
        "request": request,
        "user": user,
        "bookings": confirmed_bookings,
        "active_page": "calendar"
    })

@router.post("/api/availability/toggle")
async def toggle_availability(
    data: dict,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(auth.get_current_user) # Using current user instead of caterer_only to be safer with dict parsing
):
    if user.role != "caterer":
        raise HTTPException(status_code=403, detail="Caterer only")
        
    date_str = data.get("date")
    is_available = data.get("is_available", False)
    reason = data.get("reason", "")
    
    from datetime import datetime
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    # Check if entry already exists
    existing = db.query(models.Availability).filter(
        models.Availability.caterer_id == user.caterer_profile.id,
        models.Availability.date == target_date
    ).first()
    
    if existing:
        existing.is_available = is_available
        existing.reason = reason
    else:
        new_avail = models.Availability(
            caterer_id=user.caterer_profile.id,
            date=target_date,
            is_available=is_available,
            reason=reason
        )
        db.add(new_avail)
    
    db.commit()
    return {"status": "success"}

@router.get("/api/events")
async def get_calendar_events(
    caterer_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(auth.get_current_user_optional)
):
    # Use provided caterer_id (for customers) or user's caterer profile (for caterers themselves)
    target_caterer_id = caterer_id
    if not target_caterer_id and user and user.role == 'caterer':
        target_caterer_id = user.caterer_profile.id
    
    if not target_caterer_id:
        return []

    bookings = db.query(models.Booking).filter(
        models.Booking.caterer_id == target_caterer_id,
        models.Booking.status == 'confirmed'
    ).all()
    
    events = []
    colors = {
        "Wedding": "#ec4899", # Pink
        "Birthday": "#3b82f6", # Blue
        "Corporate": "#10b981", # Green
        "Private Party": "#f59e0b" # Orange
    }
    
    # Check if we should show full details (only for the caterer owner)
    is_owner = user and user.role == 'caterer' and user.caterer_profile.id == target_caterer_id

    for b in bookings:
        start_dt = str(b.event_date)
        if b.event_time:
            start_dt += f"T{b.event_time}"
            
        event_data = {
            "id": b.id,
            "start": start_dt,
            "backgroundColor": colors.get(b.event_type, "#6366f1"),
            "borderColor": colors.get(b.event_type, "#6366f1"),
        }

        if is_owner:
            event_data["title"] = f"{b.event_type or 'Event'} - {b.event_name or b.user.first_name}"
            event_data["extendedProps"] = {
                "customer": f"{b.user.first_name} {b.user.last_name}",
                "type": b.event_type or "N/A",
                "guests": b.guest_count,
                "venue": b.venue_address or "TBD",
                "package": b.package.name if b.package else "Custom",
                "time": str(b.event_time) if b.event_time else "TBD"
            }
        else:
            event_data["title"] = "BOOKED"
            event_data["display"] = "background"
            event_data["overlap"] = False

        events.append(event_data)
        
    # Add blocked dates from availability
    availabilities = db.query(models.Availability).filter(
        models.Availability.caterer_id == target_caterer_id,
        models.Availability.is_available == False
    ).all()
    
    for a in availabilities:
        events.append({
            "title": "BLOCKED",
            "start": str(a.date),
            "allDay": True,
            "display": "background",
            "backgroundColor": "#fee2e2",
            "overlap": False
        })
        
    return events

@router.post("/api/bookings/{booking_id}/reminders")
async def set_booking_reminder(
    booking_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    booking = db.query(models.Booking).get(booking_id)
    if not booking or booking.caterer_id != user.caterer_profile.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Simple logic: create a notification for the caterer
    new_notif = models.Notification(
        user_id=user.id,
        title=f"Reminder: {booking.event_name or 'Event'}",
        message=f"Preparation reminder for {booking.event_name} on {booking.event_date}.",
        type="reminder"
    )
    db.add(new_notif)
    db.commit()
    return {"status": "success", "message": "Reminder set successfully"}

@router.get("/notifications", response_class=HTMLResponse)
async def caterer_notifications(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == user.id
    ).order_by(models.Notification.created_at.desc()).all()
    
    return templates.TemplateResponse("caterer/notifications.html", {
        "request": request,
        "user": user,
        "notifications": notifications,
        "active_page": "notifications"
    })

@router.get("/reports", response_class=HTMLResponse)
async def caterer_reports(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    return templates.TemplateResponse("caterer/reports.html", {
        "request": request,
        "user": user,
        "bookings": user.caterer_profile.bookings,
        "active_page": "reports"
    })

@router.get("/profile", response_class=HTMLResponse)
async def caterer_profile_edit(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    return templates.TemplateResponse("caterer/profile_edit.html", {
        "request": request,
        "user": user,
        "profile": user.caterer_profile,
        "active_page": "profile"
    })

@router.post("/profile")
async def caterer_profile_update(
    request: Request,
    business_name: str = Form(...),
    description: str = Form(...),
    city: str = Form(...),
    contact_phone: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    cover_image: Optional[UploadFile] = File(None),
    gallery: Optional[list[UploadFile]] = File(None),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    profile = user.caterer_profile
    profile.business_name = business_name
    profile.description = description
    profile.city = city
    profile.contact_phone = contact_phone
    
    # Handle Logo Upload
    if logo and logo.filename:
        file_ext = os.path.splitext(logo.filename)[1]
        file_name = f"{profile.id}_logo_{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
        profile.logo_url = f"/static/uploads/caterer/{file_name}"

    # Handle Cover Image Upload
    if cover_image and cover_image.filename:
        file_ext = os.path.splitext(cover_image.filename)[1]
        file_name = f"{profile.id}_cover_{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(cover_image.file, buffer)
        profile.cover_image_url = f"/static/uploads/caterer/{file_name}"

    # Handle Gallery Uploads
    if gallery:
        for image in gallery:
            if image.filename:
                file_ext = os.path.splitext(image.filename)[1]
                file_name = f"{profile.id}_gallery_{uuid.uuid4().hex[:8]}{file_ext}"
                file_path = os.path.join(UPLOAD_DIR, file_name)
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(image.file, buffer)
                
                new_gallery_item = models.CatererGallery(
                    caterer_id=profile.id,
                    media_url=f"/static/uploads/caterer/{file_name}"
                )
                db.add(new_gallery_item)

    db.commit()
    return RedirectResponse(url="/caterer/profile", status_code=303)

@router.post("/gallery/{item_id}/delete")
async def delete_gallery_item(
    item_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    item = db.query(models.CatererGallery).get(item_id)
    if not item or item.caterer_id != user.caterer_profile.id:
        raise HTTPException(status_code=404, detail="Gallery item not found")
    
    db.delete(item)
    db.commit()
    return {"status": "success"}

@router.get("/packages", response_class=HTMLResponse)
async def caterer_packages(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    return templates.TemplateResponse("caterer/packages.html", {
        "request": request,
        "user": user,
        "packages": user.caterer_profile.packages if user.caterer_profile else [],
        "active_page": "packages"
    })

from ..services.realtime import manager

@router.post("/packages/add")
async def add_package(
    request: Request,
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(0.0), # Flat price (old field)
    min_guests: int = Form(...),
    max_guests: Optional[int] = Form(None),
    service_type: str = Form("General"),
    price_per_head: Optional[float] = Form(None),
    min_contract_amount: Optional[float] = Form(None),
    additional_guest_price: Optional[float] = Form(None),
    service_duration: int = Form(4),
    overtime_fee: float = Form(0.0),
    location_coverage: Optional[str] = Form(None),
    inclusions: list[str] = Form([]),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    # Structure inclusions as JSON
    inclusions_data = {item: True for item in inclusions}
    
    new_package = models.CateringPackage(
        caterer_id=user.caterer_profile.id,
        name=name,
        description=description,
        price=price,
        min_guests=min_guests,
        max_guests=max_guests,
        service_type=service_type,
        price_per_head=price_per_head,
        min_contract_amount=min_contract_amount,
        additional_guest_price=additional_guest_price,
        service_duration=service_duration,
        overtime_fee=overtime_fee,
        location_coverage=location_coverage,
        inclusions=inclusions_data,
        status="active"
    )
    db.add(new_package)
    db.commit()
    
    # Broadcast to all connected customers
    await manager.broadcast({
        "type": "new_package",
        "caterer_name": user.caterer_profile.business_name,
        "package_name": name,
        "caterer_id": user.caterer_profile.id
    })
    
    return RedirectResponse(url="/caterer/packages", status_code=303)

@router.get("/packages/{pkg_id}/menu")
async def get_package_menu(
    pkg_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    package = db.query(models.CateringPackage).get(pkg_id)
    if not package or package.caterer_id != user.caterer_profile.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return [
        {
            "id": i.id,
            "name": i.name,
            "category": i.category,
            "description": i.description,
            "serving_size": i.serving_size,
            "is_addon": i.is_addon,
            "addon_price": i.addon_price,
            "image_url": i.image_url
        }
        for i in package.menu_items
    ]

@router.post("/packages/{pkg_id}/delete")
async def delete_package(
    pkg_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    package = db.query(models.CateringPackage).get(pkg_id)
    if not package or package.caterer_id != user.caterer_profile.id:
        raise HTTPException(status_code=404, detail="Package not found")
    
    # Also delete associated menu items
    db.query(models.MenuItem).filter(models.MenuItem.package_id == pkg_id).delete()
    
    db.delete(package)
    db.commit()
    return {"status": "success"}

@router.post("/packages/{package_id}/menu/add")
async def add_menu_item(
    package_id: int,
    name: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    serving_size: Optional[str] = Form(None),
    is_addon: bool = Form(False),
    addon_price: float = Form(0.0),
    dietary_tags: list[str] = Form([]),
    allergen_info: list[str] = Form([]),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    package = db.query(models.CateringPackage).get(package_id)
    if not package or package.caterer_id != user.caterer_profile.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    image_url = None
    if image and image.filename:
        file_ext = os.path.splitext(image.filename)[1]
        file_name = f"dish_{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        image_url = f"/static/uploads/caterer/{file_name}"

    new_item = models.MenuItem(
        package_id=package_id,
        name=name,
        description=description,
        category=category,
        serving_size=serving_size,
        is_addon=is_addon,
        addon_price=addon_price,
        dietary_tags=dietary_tags,
        allergen_info=allergen_info,
        image_url=image_url
    )
    db.add(new_item)
    db.commit()
    return RedirectResponse(url="/caterer/packages", status_code=303)

@router.post("/packages/menu/{item_id}/delete")
async def delete_menu_item(
    item_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    item = db.query(models.MenuItem).get(item_id)
    if not item or item.package.caterer_id != user.caterer_profile.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    db.delete(item)
    db.commit()
    return {"status": "success"}
@router.post("/bookings/{booking_id}/accept")
async def accept_booking(
    request: Request,
    booking_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    booking = db.query(models.Booking).get(booking_id)
    if not booking or booking.caterer_id != user.caterer_profile.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking.status = "confirmed"
    
    history = models.BookingHistory(
        booking_id=booking.id,
        status="confirmed",
        notes="Booking accepted by caterer"
    )
    db.add(history)
    db.commit()
    
    return RedirectResponse(url="/caterer/bookings", status_code=303)

@router.post("/bookings/{booking_id}/reject")
async def reject_booking(
    request: Request,
    booking_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(caterer_only)
):
    
    booking = db.query(models.Booking).get(booking_id)
    if not booking or booking.caterer_id != user.caterer_profile.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking.status = "cancelled"
    
    history = models.BookingHistory(
        booking_id=booking.id,
        status="cancelled",
        notes="Booking rejected by caterer"
    )
    db.add(history)
    db.commit()
    
    return RedirectResponse(url="/caterer/bookings", status_code=303)
