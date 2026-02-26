import os
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from sqlalchemy.orm import Session
from datetime import timedelta
from ..db import database, models
from ..core import security as auth, utils
from ..core.config import settings

# Initialize Router
# NOTE: To use this REAL router, you must include it in main.py instead of the mock 'oauth' router.
router = APIRouter(prefix="/auth", tags=["social-auth"])

# Initialize Authlib
oauth = OAuth()

# Register Facebook
oauth.register(
    name='facebook',
    client_id=settings.FACEBOOK_CLIENT_ID,
    client_secret=settings.FACEBOOK_CLIENT_SECRET,
    access_token_url='https://graph.facebook.com/oauth/access_token',
    access_token_params=None,
    authorize_url='https://www.facebook.com/dialog/oauth',
    authorize_params=None,
    api_base_url='https://graph.facebook.com/',
    client_kwargs={'scope': 'email public_profile'},
)

# Register Google
oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
    authorize_params={'prompt': 'select_account'},
)

# Register Instagram
oauth.register(
    name='instagram',
    client_id=settings.INSTAGRAM_CLIENT_ID,
    client_secret=settings.INSTAGRAM_CLIENT_SECRET,
    authorize_url='https://api.instagram.com/oauth/authorize',
    access_token_url='https://api.instagram.com/oauth/access_token',
    api_base_url='https://graph.instagram.com/',
    client_kwargs={'scope': 'user_profile,user_media'},
)

@router.get("/login/{provider}")
async def social_login(request: Request, provider: str):
    """
    Redirects the user to the social provider's login page.
    Real OAuth flow using Authlib.
    """
    # Fix for Mismatching State (CSRF): Domain Consistency Check
    # If user is on localhost but SITE_URL is set to ngrok, redirect them to ngrok first.
    # Browsers cannot share session cookies between localhost and ngrok.
    current_host = request.base_url.hostname
    target_host = settings.SITE_URL.split("//")[-1].split("/")[0].split(":")[0]
    
    if (current_host == "127.0.0.1" or current_host == "localhost") and "ngrok-free.dev" in target_host:
        # Construct the target URL on the ngrok domain
        new_url = f"{settings.SITE_URL.rstrip('/')}{request.url.path}"
        query_params = str(request.query_params)
        if query_params:
            new_url += f"?{query_params}"
        print(f"DEBUG DOMAIN FIX: Redirecting from {current_host} to {new_url}")
        return RedirectResponse(url=new_url)

    client = oauth.create_client(provider)
    
    # Simple and robust config check
    configs = {
        'facebook': settings.FACEBOOK_CLIENT_ID,
        'google': settings.GOOGLE_CLIENT_ID,
        'instagram': settings.INSTAGRAM_CLIENT_ID
    }
    config_id = configs.get(provider)

    if not client or not config_id:
        print(f"DEBUG ERROR: Missing config for {provider}. Config ID: '{config_id}'")
        return RedirectResponse(url=f"/auth/login?error=config_missing&provider={provider}")
        
    # Construct redirect_uri using SITE_URL from config
    site_url = settings.SITE_URL.rstrip('/')
    redirect_uri = f"{site_url}/auth/callback/{provider}"
    
    # Fallback for localhost development if SITE_URL is default
    if "127.0.0.1" in redirect_uri and "ngrok-free.dev" in str(request.base_url):
        redirect_uri = str(request.url_for('auth_callback', provider=provider)).replace("http://", "https://")
    
    return await client.authorize_redirect(request, redirect_uri)

@router.get("/callback/{provider}", name="auth_callback")
async def auth_callback(request: Request, provider: str, db: Session = Depends(database.get_db)):
    """
    Handles the callback from the provider, exchanges code for token,
    and logs in/registers the user.
    """
    try:
        # Authlib automatically retrieves state and redirect_uri from the session
        token = await oauth.create_client(provider).authorize_access_token(request)
    except OAuthError as error:
        print(f"OAUTH ERROR: {error}")
        # Pass the error description to help debug
        error_msg = str(error)
        return RedirectResponse(url=f"/auth/login?error=oauth_failed&details={error_msg}")

    # --- 1. HANDLE EXTERNAL INFO ---
    user_info = None
    email = None
    social_id = None
    name = None
    picture = None
    
    if provider == 'facebook':
        # Request specific fields from Facebook
        resp = await oauth.facebook.get('me?fields=id,name,email,picture', token=token)
        user_info = resp.json()
        social_id = user_info.get('id')
        email = user_info.get('email') # Might be None if user didn't grant email permission
        name = user_info.get('name')
        picture = user_info.get('picture', {}).get('data', {}).get('url')
        
    elif provider == 'google':
        user_info = token.get('userinfo')
        if not user_info:
            resp = await oauth.google.get('https://openidconnect.googleapis.com/v1/userinfo', token=token)
            user_info = resp.json()
        social_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture')

    elif provider == 'instagram':
        resp = await oauth.instagram.get('me?fields=id,username', token=token)
        user_info = resp.json()
        social_id = user_info.get('id')
        name = user_info.get('username')
        # Instagram API doesn't always provide email; use a placeholder
        email = f"{social_id}@instagram.user" 
        picture = None

    # --- 2. DATABASE SYNCHRONIZATION ---
    user = None
    
    # Priority A: Check by Social ID (Most reliable for social login)
    if provider == 'facebook':
        user = db.query(models.User).filter(models.User.facebook_id == social_id).first()
    elif provider == 'google':
        user = db.query(models.User).filter(models.User.google_id == social_id).first()
    elif provider == 'instagram':
        user = db.query(models.User).filter(models.User.instagram_id == social_id).first()

    # Priority B: Check by Email if Social ID check failed
    if not user and email:
        user = db.query(models.User).filter(models.User.email == email).first()
    
    # --- 3. AUTO-CREATE OR UPDATE ACCOUNT ---
    if not user:
        # Create New User
        # If email is missing, we use a placeholder that the user must update in onboarding
        final_email = email if email else f"fb_{social_id}@no-email.com"
        
        user = models.User(
            email=final_email,
            password_hash=auth.get_password_hash(os.urandom(16).hex()), # Unusable random password
            first_name=name.split(" ")[0] if name else "User",
            last_name=name.split(" ")[-1] if name and " " in name else "",
            role="customer", # Default role as requested
            status="active",
            is_email_verified=True if email else False, # Verified if we got it from provider
            auth_provider=provider,
            profile_image_url=picture
        )
        if provider == 'facebook': user.facebook_id = social_id
        if provider == 'google': user.google_id = social_id
        if provider == 'instagram': user.instagram_id = social_id
        
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Handle existing account: Link social ID if missing
        updated = False
        if provider == 'facebook' and not user.facebook_id:
            user.facebook_id = social_id
            updated = True
        elif provider == 'google' and not user.google_id:
            user.google_id = social_id
            updated = True
        elif provider == 'instagram' and not user.instagram_id:
            user.instagram_id = social_id
            updated = True
        
        if updated:
            db.commit()

    # Create Session Token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    # Check if profile is complete
    # Force onboarding if:
    # 1. Role is pending (from old logic)
    # 2. Email is a placeholder (missing from provider)
    # 3. Customer is missing phone or address
    is_placeholder_email = user.email.endswith("@no-email.com")
    
    if user.role == "pending" or is_placeholder_email or (user.role == "customer" and (not user.phone_number or not user.address)):
        redirect_url = "/auth/onboarding"
        if is_placeholder_email:
            redirect_url += "?reason=missing_email"
    else:
        redirect_url = utils.get_dashboard_url(user.role)

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response
