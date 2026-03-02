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
    
    # Caterer Metrics
    total_caterers = db.query(models.CatererProfile).count()
    pending_caterers = db.query(models.CatererProfile).filter(models.CatererProfile.verification_status == "Pending").all()
    approved_caterers_count = db.query(models.CatererProfile).filter(models.CatererProfile.verification_status == "Verified").count()
    rejected_caterers_count = db.query(models.CatererProfile).filter(models.CatererProfile.verification_status == "Rejected").count()
    
    all_bookings = db.query(models.Booking).all()
    booking_count = len(all_bookings)
    
    total_sales = sum(b.total_amount for b in all_bookings if b.status != 'cancelled')
    total_revenue = sum(b.total_amount for b in all_bookings if b.payment_status == 'paid')
    platform_earnings = total_revenue * 0.10 # 10% commission

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
            "caterer_count": total_caterers,
            "pending_caterers_count": len(pending_caterers),
            "approved_caterers_count": approved_caterers_count,
            "rejected_caterers_count": rejected_caterers_count,
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
    
    # Caterer Metrics for Summary
    metrics = {
        "total_caterers": db.query(models.CatererProfile).count(),
        "pending_caterers_count": db.query(models.CatererProfile).filter(models.CatererProfile.verification_status == "Pending").count(),
        "approved_caterers_count": db.query(models.CatererProfile).filter(models.CatererProfile.verification_status == "Verified").count(),
        "rejected_caterers_count": db.query(models.CatererProfile).filter(models.CatererProfile.verification_status == "Rejected").count(),
    }

    return templates.TemplateResponse("admin/caterers.html", {
        "request": request,
        "user": user,
        "caterers": caterers,
        "metrics": metrics,
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
def verify_caterer(
    caterer_id: int, 
    action: str = Form(...), 
    reason: Optional[str] = Form(None),
    db: Session = Depends(database.get_db), 
    user: models.User = Depends(admin_only)
):
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
    elif action == "reject":
        caterer.verification_status = "Rejected"
        caterer.is_verified = False
        # Optional: Store rejection reason if we added a field for it, 
        # or send a notification/email to the caterer.
    elif action == "revision":
        caterer.verification_status = "Revision Requested"
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

@router.post("/customers/{customer_id}/delete")
def delete_customer(customer_id: int, db: Session = Depends(database.get_db), user: models.User = Depends(admin_only)):
    # Find the user as a customer only to be safe
    customer = db.query(models.User).filter(models.User.id == customer_id, models.User.role == "customer").first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Manually delete related data that doesn't have cascade-delete or might cause issues
    db.query(models.RefreshToken).filter(models.RefreshToken.user_id == customer_id).delete()
    db.query(models.IdentityVerification).filter(models.IdentityVerification.user_id == customer_id).delete()
    db.query(models.AuditLog).filter(models.AuditLog.user_id == customer_id).delete()
    db.query(models.Notification).filter(models.Notification.user_id == customer_id).delete()
    db.query(models.VerificationAttempt).filter(models.VerificationAttempt.user_id == customer_id).delete()
    db.query(models.Review).filter(models.Review.user_id == customer_id).delete()
    db.query(models.Inquiry).filter(models.Inquiry.user_id == customer_id).delete()
    db.query(models.OCRVerification).filter(models.OCRVerification.user_id == customer_id).delete()
    
    # Finally delete the user
    db.delete(customer)
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

@router.post("/bookings/{booking_id}/manual_confirm")
def manual_confirm_booking_payment(
    booking_id: int, 
    db: Session = Depends(database.get_db), 
    user: models.User = Depends(admin_only)
):
    booking = db.query(models.Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    booking.payment_status = "paid"
    booking.status = "confirmed"
    booking.payment_reference = "MANUAL_ADMIN_OVERRIDE"
    
    # Add history log
    log = models.BookingHistory(
        booking_id=booking.id,
        status="confirmed",
        notes=f"Payment manually confirmed by Admin {user.first_name} {user.last_name}."
    )
    db.add(log)
    db.commit()
    
    return RedirectResponse(url="/admin/bookings", status_code=status.HTTP_303_SEE_OTHER)

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
    # Get all verifications in process or manual review
    kyc_requests = db.query(models.IdentityVerification).filter(
        models.IdentityVerification.verification_status.in_(["manual_review", "processing"])
    ).all()
    
    return templates.TemplateResponse("admin/kyc_logs.html", {
        "request": request,
        "user": user,
        "kyc_requests": kyc_requests,
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
    
    kyc = db.query(models.IdentityVerification).filter(models.IdentityVerification.user_id == booking.user_id).first()
    audit_trail = db.query(models.AuditLog).filter(models.AuditLog.user_id == booking.user_id).order_by(models.AuditLog.timestamp.desc()).all()
    
    return templates.TemplateResponse("admin/booking_kyc.html", {
        "request": request,
        "user": user,
        "booking": booking,
        "kyc": kyc,
        "audit_trail": audit_trail,
        "active_page": "bookings"
    })

@router.post("/kyc/{kyc_id}/action")
async def kyc_manual_action(
    kyc_id: int,
    action: str = Form(...),
    notes: str = Form(None),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    kyc = db.query(models.IdentityVerification).get(kyc_id)
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC record not found")
    
    target_user = db.query(models.User).get(kyc.user_id)
    
    if action == "approve":
        kyc.verification_status = "approved"
        target_user.is_verified = True
        target_user.is_kyc_complete = True
    else:
        kyc.verification_status = "rejected"
        kyc.failure_reason = notes or "Rejected after manual review."
    
    # Audit Log
    audit = models.AuditLog(
        user_id=target_user.id,
        action="manual_kyc_decision",
        old_status="manual_review",
        new_status=kyc.verification_status,
        notes=f"Admin {user.email}: {notes}"
    )
    db.add(audit)
    db.commit()
    
    return RedirectResponse(url="/admin/kyc", status_code=303)

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

@router.get("/payouts", response_class=HTMLResponse)
async def admin_payouts(
    request: Request,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    # Get all un-payout-ed paid bookings to group them by Caterer
    holding_bookings = db.query(models.Booking).filter(
        models.Booking.payment_status == "paid",
        models.Booking.payout_id == None,
        models.Booking.status.in_(["completed", "confirmed"]) # Typically paid and event done or verified
    ).all()
    
    # Calculate holding by Caterer
    caterer_holdings = {}
    for b in holding_bookings:
        if b.caterer_id not in caterer_holdings:
            caterer_holdings[b.caterer_id] = {
                "caterer": b.caterer,
                "total_held": 0.0,
                "booking_count": 0,
                "booking_ids": []
            }
        
        # Calculate caterer's cut (assuming 10% platform fee)
        net_amount = float(b.reservation_fee or 0.0) * 0.90
        
        caterer_holdings[b.caterer_id]["total_held"] += float(net_amount)
        caterer_holdings[b.caterer_id]["booking_count"] += 1
        caterer_holdings[b.caterer_id]["booking_ids"].append(b.id)
        
    # Get all existing payout records
    payout_history = db.query(models.Payout).order_by(models.Payout.created_at.desc()).all()
    
    return templates.TemplateResponse("admin/payouts.html", {
        "request": request,
        "user": user,
        "caterer_holdings": caterer_holdings.values(),
        "payout_history": payout_history,
        "active_page": "financials"
    })

@router.post("/payouts/create")
async def create_payout(
    caterer_id: int = Form(...),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    # Get all eligible holdings for this caterer
    bookings = db.query(models.Booking).filter(
        models.Booking.caterer_id == caterer_id,
        models.Booking.payment_status == "paid",
        models.Booking.payout_id == None,
        models.Booking.status.in_(["completed", "confirmed"])
    ).all()
    
    if not bookings:
        raise HTTPException(status_code=400, detail="No eligible bookings found for payout")
        
    total_net = 0.0
    for b in bookings:
        total_net += float(b.reservation_fee or 0.0) * 0.90
        
    new_payout = models.Payout(
        caterer_id=caterer_id,
        amount=total_net,
        status="processing",
        notes="Generated automatically by Admin."
    )
    db.add(new_payout)
    db.flush() # get ID
    
    # Link bookings
    for b in bookings:
        item = models.PayoutItem(
            payout_id=new_payout.id,
            booking_id=b.id,
            amount=float(b.reservation_fee or 0.0) * 0.90
        )
        db.add(item)
        b.payout_id = new_payout.id
        
    db.commit()
    return RedirectResponse(url="/admin/payouts", status_code=303)

@router.post("/payouts/{payout_id}/mark_paid")
async def mark_payout_paid(
    payout_id: int,
    reference_number: str = Form(...),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    payout = db.query(models.Payout).get(payout_id)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
        
    from datetime import datetime, timezone
    payout.status = "completed"
    payout.reference_number = reference_number
    payout.completed_at = datetime.now(timezone.utc)
    
    db.commit()
    return RedirectResponse(url="/admin/payouts", status_code=303)

@router.get("/api/reports/export")
async def export_reports(
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    # Mock CSV export
    return {"message": "Export started. You will receive an email shortly."}

@router.get("/reviews", response_class=HTMLResponse)
async def admin_reviews(
    request: Request,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    reviews = db.query(models.Review).order_by(models.Review.created_at.desc()).all()
    return templates.TemplateResponse("admin/reviews.html", {
        "request": request,
        "user": user,
        "reviews": reviews,
        "active_page": "reviews"
    })

@router.post("/reviews/{review_id}/highlight")
async def toggle_review_highlight(
    review_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    review = db.query(models.Review).get(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    review.is_highlighted = not review.is_highlighted
    db.commit()
    return RedirectResponse(url="/admin/reviews", status_code=303)

@router.post("/reviews/{review_id}/delete")
async def delete_review(
    review_id: int,
    db: Session = Depends(database.get_db),
    user: models.User = Depends(admin_only)
):
    review = db.query(models.Review).get(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    db.delete(review)
    db.commit()
    return RedirectResponse(url="/admin/reviews", status_code=303)
