from fastapi import APIRouter, Depends, HTTPException, status, Form
from typing import Optional
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..db import database, models
from ..core import security as auth

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")

# Standard dependency for admin access
admin_only = auth.RoleChecker(["admin"])

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):

    # Platform Metrics
    user_count = db.query(models.User).count()
    customer_count = db.query(models.User).filter(models.User.role == 'customer').count()
    caterer_count = db.query(models.CatererProfile).count()
    
    all_bookings = db.query(models.Booking).all()
    booking_count = len(all_bookings)
    
    total_sales = sum(b.total_amount for b in all_bookings if b.status != 'cancelled')
    total_revenue = sum(b.total_amount for b in all_bookings if b.payment_status == 'paid')
    platform_earnings = total_revenue * 0.10 # 10% commission

    pending_caterers = db.query(models.CatererProfile).filter(models.CatererProfile.verification_status == "Pending").all()
    pending_customers = db.query(models.User).filter(
        models.User.role == "customer",
        models.User.is_verified == False
    ).all()

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": user,
        "metrics": {
            "user_count": user_count,
            "customer_count": customer_count,
            "caterer_count": caterer_count,
            "booking_count": booking_count,
            "total_sales": total_sales,
            "total_revenue": total_revenue,
            "platform_earnings": platform_earnings,
            "pending_verifications": len(pending_caterers) + len(pending_customers)
        },
        "pending_caterers": pending_caterers,
        "active_page": "overview"
    })

@router.get("/caterers", response_class=HTMLResponse)
async def manage_caterers(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    
    caterers = db.query(models.CatererProfile).all()
    return templates.TemplateResponse("admin/caterers.html", {
        "request": request,
        "user": user,
        "caterers": caterers,
        "active_page": "caterers"
    })

@router.get("/customers", response_class=HTMLResponse)
async def manage_customers(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    
    customers = db.query(models.User).filter(models.User.role == 'customer').all()
    return templates.TemplateResponse("admin/customers.html", {
        "request": request,
        "user": user,
        "customers": customers,
        "active_page": "customers"
    })

@router.get("/bookings", response_class=HTMLResponse)
async def all_bookings(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    
    bookings = db.query(models.Booking).all()
    return templates.TemplateResponse("admin/bookings.html", {
        "request": request,
        "user": user,
        "bookings": bookings,
        "active_page": "bookings"
    })

@router.get("/payments", response_class=HTMLResponse)
async def platform_payments(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    
    bookings = db.query(models.Booking).all()
    return templates.TemplateResponse("admin/payments.html", {
        "request": request,
        "user": user,
        "bookings": bookings,
        "active_page": "payments"
    })

@router.get("/reviews", response_class=HTMLResponse)
async def platform_reviews(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    
    reviews = db.query(models.Review).all()
    return templates.TemplateResponse("admin/reviews.html", {
        "request": request,
        "user": user,
        "reviews": reviews,
        "active_page": "reviews"
    })

@router.get("/reports", response_class=HTMLResponse)
async def admin_reports(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    
    return templates.TemplateResponse("admin/reports.html", {
        "request": request,
        "user": user,
        "active_page": "reports"
    })

@router.get("/settings", response_class=HTMLResponse)
async def website_settings(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    
    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "user": user,
        "active_page": "settings"
    })

@router.post("/caterers/{caterer_id}/verify")
def verify_caterer(caterer_id: int, action: str = Form(...), db: Session = Depends(database.get_db), user: models.User = Depends(admin_only)):
    caterer = db.query(models.CatererProfile).get(caterer_id)
    if not caterer:
        raise HTTPException(status_code=404, detail="Caterer not found")
    
    if action == "approve":
        caterer.verification_status = "Verified"
        caterer.is_verified = True
        # Explicitly activate the associated user account and clear all barriers
        if caterer.user_id:
            caterer_user = db.query(models.User).get(caterer.user_id)
            if caterer_user:
                caterer_user.status = "active"
                caterer_user.is_email_verified = True
                caterer_user.is_verified = True
    else:
        caterer.verification_status = "Rejected"
        caterer.is_verified = False
    
    db.commit()
    return RedirectResponse(url="/admin/caterers", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/caterers/{caterer_id}/status")
def toggle_caterer_status(caterer_id: int, db: Session = Depends(database.get_db), user: models.User = Depends(admin_only)):
    caterer = db.query(models.CatererProfile).get(caterer_id)
    if not caterer:
        raise HTTPException(status_code=404, detail="Caterer not found")
    
    # Toggle status of the associated user account using direct lookup
    if caterer.user_id:
        caterer_user = db.query(models.User).get(caterer.user_id)
        if caterer_user:
            if caterer_user.status == "active":
                caterer_user.status = "suspended"
            else:
                # Activate and clear barriers if coming from suspended or pending
                caterer_user.status = "active"
                caterer_user.is_email_verified = True
                caterer_user.is_verified = True
    
    db.commit()
    return RedirectResponse(url="/admin/caterers", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/customers/{customer_id}/status")
def toggle_customer_status(customer_id: int, db: Session = Depends(database.get_db), user: models.User = Depends(admin_only)):
    customer = db.query(models.User).filter(models.User.id == customer_id, models.User.role == "customer").first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if customer.status == "active":
        customer.status = "suspended"
    else:
        customer.status = "active"
        customer.is_email_verified = True
        customer.is_verified = True
        
    db.commit()
    return RedirectResponse(url="/admin/customers", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/customers/{customer_id}/verify")
def verify_customer(customer_id: int, action: str = Form(...), db: Session = Depends(database.get_db), user: models.User = Depends(admin_only)):
    customer = db.query(models.User).filter(models.User.id == customer_id, models.User.role == "customer").first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if action == "approve":
        customer.is_verified = True
        customer.is_email_verified = True
        customer.status = "active"
    else:
        customer.is_verified = False
    
    db.commit()
    return RedirectResponse(url="/admin/customers", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/verify/{user_id}", response_class=HTMLResponse)
async def view_verification(
    user_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    target_user = db.query(models.User).get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get identity verification or caterer profile
    verification = target_user.identity_verification
    caterer_profile = target_user.caterer_profile
    
    return templates.TemplateResponse("admin/verification_detail.html", {
        "request": request,
        "user": user,
        "target_user": target_user,
        "verification": verification,
        "caterer_profile": caterer_profile,
        "active_page": target_user.role + "s"
    })

@router.get("/kyc")
async def view_kyc_queue(
    request: Request,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    high_risk_bookings = db.query(models.Booking).filter(
        models.Booking.status.in_(["flagged", "pending"])
    ).all()
    
    return templates.TemplateResponse("admin/kyc_logs.html", {
        "request": request,
        "user": user,
        "high_risk_bookings": high_risk_bookings,
        "active_page": "kyc"
    })

# --- New KYC & Fraud Admin Endpoints ---

@router.get("/api/bookings")
async def api_list_bookings(
    status: Optional[str] = None,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    query = db.query(models.Booking)
    if status:
        query = query.filter(models.Booking.status == status)
    return query.all()

@router.get("/bookings/{booking_id}/kyc")
async def view_booking_kyc(
    booking_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    booking = db.query(models.Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    kyc_results = db.query(models.OCRVerification).filter(models.OCRVerification.booking_id == booking_id).first()
    fraud_flags = db.query(models.FraudFlag).filter(models.FraudFlag.booking_id == booking_id).all()
    
    return templates.TemplateResponse("admin/booking_kyc.html", {
        "request": request,
        "user": user,
        "booking": booking,
        "kyc": kyc_results,
        "flags": fraud_flags,
        "active_page": "bookings"
    })

@router.post("/bookings/{booking_id}/flag")
async def flag_booking(
    booking_id: int,
    flag_type: str = Form(...),
    description: str = Form(...),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    flag = models.FraudFlag(
        booking_id=booking_id,
        flag_type=flag_type,
        description=description
    )
    db.add(flag)
    db.commit()
    return RedirectResponse(url=f"/admin/bookings/{booking_id}/kyc", status_code=303)

@router.get("/api/reports/export")
async def export_reports(
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    # Mock CSV export
    return {"message": "Export started. You will receive an email shortly."}

