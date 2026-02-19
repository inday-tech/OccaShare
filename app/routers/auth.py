from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, File, UploadFile
from jose import JWTError, jwt
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import EmailStr, ValidationError

from ..db import database, schemas, models
from ..core import security as auth, utils

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "app/static/uploads/verification"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, next: Optional[str] = None):
    return templates.TemplateResponse("auth/register.html", {"request": request, "next_url": next})

@router.get("/register/caterer", response_class=HTMLResponse)
def register_caterer_page(request: Request, next: Optional[str] = None):
    return templates.TemplateResponse("auth/register_caterer.html", {"request": request, "next_url": next})

@router.post("/register")
async def register(
    request: Request,
    role: str = Form("customer"),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    mobile_number: str = Form(...),
    address: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    # Caterer fields
    business_name: str = Form(None),
    business_type: str = Form(None),
    years_of_operation: int = Form(0),
    business_description: str = Form(None),
    coverage_area: str = Form(None),
    payout_method: str = Form(None),
    payout_account_name: Optional[str] = Form(None),
    account_number: Optional[str] = Form(None),
    event_types: Optional[str] = Form(None),
    min_pax: int = Form(0),
    starting_price: float = Form(0.0),
    city: str = Form(None),
    # Verification Files & Logo
    logo: UploadFile = File(None),
    gov_id: UploadFile = File(None),
    permit: UploadFile = File(None),
    sample_menu: UploadFile = File(None),
    next_url: Optional[str] = Form(None),
    db: Session = Depends(database.get_db)
):
    # server‑side validation
    errors: List[str] = []
    try:
        from pydantic import TypeAdapter
        TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        errors.append("Invalid email address")

    if not first_name.strip() or not last_name.strip():
        errors.append("First and last names are required")

    if not mobile_number.isdigit():
        errors.append("Mobile number must contain only digits")

    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if password != confirm_password:
        errors.append("Passwords do not match")

    if role == "caterer":
        if not business_name or not business_name.strip():
            errors.append("Business name is required for caterers")
        # Removed coverage_area requirement per user request

    if errors:
        context = {"request": request, "error": "; ".join(errors), "next_url": next_url, "role": role}
        template = "auth/register_caterer.html" if role == "caterer" else "auth/register.html"
        return templates.TemplateResponse(template, context)

    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        template = "auth/register_caterer.html" if role == "caterer" else "auth/register.html"
        return templates.TemplateResponse(template, {
            "request": request,
            "error": "Email already registered",
            "next_url": next_url,
            "role": role
        })
    
    hashed_password = auth.get_password_hash(password)
    
    # Names are already provided separately

    otp = utils.get_random_digits(6)
    # Set expiration to 1 minute from now
    otp_expires_at = func.now() + timedelta(minutes=1)
    
    new_user = models.User(
        email=email, 
        password_hash=hashed_password,
        role=role, 
        first_name=first_name,
        last_name=last_name,
        phone_number=mobile_number,
        status="pending_approval" if role == "caterer" else "active",
        is_verified=False,
        is_email_verified=False,
        verification_code=otp,
        otp_expires_at=otp_expires_at
    )
    db.add(new_user)
    db.flush() # Get user ID without committing
    
    # Save files and create verification record if caterer
    if role == "caterer":
        gov_id_url = ""
        permit_url = ""
        sample_menu_url = ""
        logo_url = "/static/images/default_caterer.png"
        
        # Ensure upload directory for profiles
        PROFILE_DIR = "app/static/uploads/profiles"
        os.makedirs(PROFILE_DIR, exist_ok=True)

        if logo and logo.filename:
            file_ext = os.path.splitext(logo.filename)[1]
            file_name = f"{new_user.id}_logo{file_ext}"
            file_path = os.path.join(PROFILE_DIR, file_name)
            with open(file_path, "wb") as buffer:
                buffer.write(await logo.read())
            logo_url = f"/static/uploads/profiles/{file_name}"

        if gov_id and gov_id.filename:
            file_path = os.path.join(UPLOAD_DIR, f"{new_user.id}_gov_id_{gov_id.filename}")
            with open(file_path, "wb") as buffer:
                buffer.write(await gov_id.read())
            gov_id_url = f"/static/uploads/verification/{new_user.id}_gov_id_{gov_id.filename}"
            
        if permit and permit.filename:
            file_path = os.path.join(UPLOAD_DIR, f"{new_user.id}_permit_{permit.filename}")
            with open(file_path, "wb") as buffer:
                buffer.write(await permit.read())
            permit_url = f"/static/uploads/verification/{new_user.id}_permit_{permit.filename}"

        if sample_menu and sample_menu.filename:
            file_path = os.path.join(UPLOAD_DIR, f"{new_user.id}_menu_{sample_menu.filename}")
            with open(file_path, "wb") as buffer:
                buffer.write(await sample_menu.read())
            sample_menu_url = f"/static/uploads/verification/{new_user.id}_menu_{sample_menu.filename}"

        # Handle event_types
        event_list = []
        if event_types:
            event_list = [e.strip() for e in event_types.split(",") if e.strip()]

        new_profile = models.CatererProfile(
            user_id=new_user.id,
            business_name=business_name,
            business_type=business_type,
            years_of_operation=years_of_operation,
            description=business_description,
            coverage_area=coverage_area,
            payout_method=payout_method,
            payout_account_name=payout_account_name,
            payout_account_number=account_number,
            contact_address=address,
            contact_phone=mobile_number,
            logo_url=logo_url,
            event_types=event_list,
            min_pax=min_pax,
            starting_price=starting_price,
            city=city,
            sample_menu_url=sample_menu_url,
            permit_url=permit_url,
            gov_id_url=gov_id_url,
            verification_status="Pending"
        )
        db.add(new_profile)

        # Simulate OCR Data Extraction
        ocr_simulated_data = {
            "extracted_business_name": business_name,
            "document_type": "Business Permit",
            "confidence": 0.98,
            "verification_check_passed": True,
            "extracted_at": datetime.now().isoformat()
        }

        # Create IdentityVerification record for the documents
        if gov_id_url or permit_url:
            verification = models.IdentityVerification(
                user_id=new_user.id,
                document_url=gov_id_url,
                selfie_url=permit_url, # Using selfie_url for permit as a placeholder/second doc
                ocr_data=ocr_simulated_data,
                verification_status="pending"
            )
            db.add(verification)
    
    db.commit()
    db.refresh(new_user)
    
    # Send Email
    from ..services.email import EmailService
    EmailService.send_verification_email(email, otp)
    
    verify_url = f"/auth/verify?email={email}"
    if next_url:
        verify_url += f"&next={next_url}"
        
    return RedirectResponse(url=verify_url, status_code=status.HTTP_303_SEE_OTHER)

@router.get("/verify", response_class=HTMLResponse)
def verify_email_page(request: Request, email: str = "", next: Optional[str] = None):
    return templates.TemplateResponse("auth/verify_email.html", {"request": request, "email": email, "next_url": next})

@router.post("/verify")
def verify_email_submit(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    next_url: Optional[str] = Form(None),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
         return templates.TemplateResponse("auth/verify_email.html", {
            "request": request, 
            "email": email,
            "error": "User not found"
        })
        
    if user.verification_code == code:
        # Check if code is expired
        from datetime import datetime
        if user.otp_expires_at and user.otp_expires_at < datetime.now(user.otp_expires_at.tzinfo):
            return templates.TemplateResponse("auth/verify_email.html", {
                "request": request, 
                "email": email,
                "error": "Verification code has expired. Please request a new one."
            })

        user.is_email_verified = True
        user.verification_code = None # Clear code
        user.otp_expires_at = None # Clear expiration
        
        # Update last_login
        from sqlalchemy.sql import func
        user.last_login = func.now()
        db.commit()
        
        # Auto Login after Verification
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth.create_access_token(
            data={"sub": user.email, "role": user.role},
            expires_delta=access_token_expires
        )
        
        # Smart Redirect
        redirect_url = next_url if next_url else utils.get_dashboard_url(user.role)
            
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
        return response
    else:
        return templates.TemplateResponse("auth/verify_email.html", {
            "request": request, 
            "email": email,
            "error": "Invalid verification code"
        })

@router.post("/resend-code")
def resend_verification_code(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {"success": False, "message": "User not found"}
        
    if user.is_email_verified:
        return {"success": False, "message": "Email already verified"}

    # Generate new OTP
    otp = utils.get_random_digits(6)
    user.verification_code = otp
    user.otp_expires_at = func.now() + timedelta(minutes=1)
    db.commit()
    
    # Resend Email
    from ..services.email import EmailService
    EmailService.send_verification_email(email, otp)
    
    return {"success": True, "message": "Verification code resent"}

@router.get("/verify-status")
def check_verify_status(email: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {"verified": False}
    return {"verified": user.is_email_verified}

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: Optional[str] = None, db: Session = Depends(database.get_db)):
    # Check if already logged in
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
        user = auth.verify_token(token, db)
        if user:
            return RedirectResponse(url=next if next else utils.get_dashboard_url(user.role))
            
    return templates.TemplateResponse("auth/login.html", {"request": request, "next_url": next})

@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_url: Optional[str] = Form(None),
    db: Session = Depends(database.get_db)
):
    # basic validation
    if not email or not password:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Email and password are required",
            "next_url": next_url
        })
    try:
        from pydantic import TypeAdapter
        TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid email address",
            "next_url": next_url
        })

    search_email = email
    if email.lower() == "admin":
        search_email = "admin@occaserve.com"
        
    user = db.query(models.User).filter(func.lower(models.User.email) == search_email.lower().strip()).first()

    if not user or not auth.verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid credentials",
            "next_url": next_url
        })
    
    if user.status != "active":
         return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Account is inactive or pending approval."
        })
        
    if not user.is_email_verified and user.role != "admin":
        # Check if auth provider is email, if social it should be verified
        if user.auth_provider == 'email':
             return templates.TemplateResponse("auth/login.html", {
                "request": request,
                "error": "Please verify your email address before logging in.",
                "verification_needed": True,
                "email": email,
                "next_url": next_url
            })

    # Update last_login
    user.last_login = func.now()
    db.commit()

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email, "role": user.role}, # Include role in token
        expires_delta=access_token_expires
    )
    
    # Smart Redirect
    redirect_url = next_url if next_url else utils.get_dashboard_url(user.role)

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse("auth/forgot_password.html", {"request": request})

@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        token = str(uuid.uuid4())
        user.reset_token = token
        user.reset_token_expires = datetime.now() + timedelta(hours=1)
        db.commit()
        
        # Send Email
        from ..services.email import EmailService
        EmailService.send_password_reset_email(email, token)
        
    # Always return success message for security (don't reveal if email exists)
    return templates.TemplateResponse("auth/forgot_password.html", {
        "request": request,
        "success": "If your email is registered, you will receive a reset link shortly."
    })

@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse("auth/reset_password.html", {"request": request, "token": token})

@router.post("/reset-password")
async def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(
        models.User.reset_token == token,
        models.User.reset_token_expires > datetime.now()
    ).first()
    
    if not user:
        return templates.TemplateResponse("auth/forgot_password.html", {
            "request": request,
            "error": "Invalid or expired reset token. Please request a new one."
        })
        
    user.password_hash = auth.get_password_hash(password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    
    return RedirectResponse(url="/auth/login?success=password_reset", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
def logout():
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response
