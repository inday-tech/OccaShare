import os
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from sqlalchemy.orm import Session
from datetime import timedelta
from ..db import database, models
from ..core import security as auth
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
    redirect_uri = request.url_for('auth_callback', provider=provider)
    return await oauth.create_client(provider).authorize_redirect(request, redirect_uri)

@router.get("/callback/{provider}", name="auth_callback")
async def auth_callback(request: Request, provider: str, db: Session = Depends(database.get_db)):
    """
    Handles the callback from the provider, exchanges code for token,
    and logs in/registers the user.
    """
    try:
        token = await oauth.create_client(provider).authorize_access_token(request)
    except OAuthError as error:
        # In production, handle this gracefully (e.g. user denied access)
        return RedirectResponse(url="/login?error=oauth_failed")

    user_info = None
    email = None
    social_id = None
    
    if provider == 'facebook':
        resp = await oauth.facebook.get('me?fields=id,name,email,picture', token=token)
        user_info = resp.json()
        social_id = user_info.get('id')
        email = user_info.get('email')
        name = user_info.get('name')
        picture = user_info.get('picture', {}).get('data', {}).get('url')
        
    elif provider == 'instagram':
        # Instagram Basic Display API (Simplified)
        resp = await oauth.instagram.get('me?fields=id,username', token=token)
        user_info = resp.json()
        social_id = user_info.get('id')
        name = user_info.get('username')
        # Instagram Basic Display does NOT return email usually.
        # We might need to ask the user for email or use a placeholder.
        email = f"{social_id}@instagram.user" 
        picture = None # Requires additional permission

    # DB Synchronization
    user = None
    if email:
        user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        # Check by Social ID if email changed or missing
        if provider == 'facebook':
            user = db.query(models.User).filter(models.User.facebook_id == social_id).first()
        elif provider == 'instagram':
            user = db.query(models.User).filter(models.User.instagram_id == social_id).first()
            
    if not user:
        # Create New User
        user = models.User(
            email=email,
            password_hash=auth.get_password_hash("social_login_dummy_password"), # Unusable password
            first_name=name.split(" ")[0] if name else "User",
            last_name=name.split(" ")[-1] if name and " " in name else "",
            role="customer",
            status="active",
            is_email_verified=True, # Trust social provider
            auth_provider=provider,
            profile_image_url=picture
        )
        if provider == 'facebook': user.facebook_id = social_id
        if provider == 'instagram': user.instagram_id = social_id
        
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update Existing User
        if provider == 'facebook' and not user.facebook_id:
            user.facebook_id = social_id
            user.auth_provider = 'facebook' # Link account
            if not user.is_email_verified: user.is_email_verified = True
        elif provider == 'instagram' and not user.instagram_id:
            user.instagram_id = social_id
            user.auth_provider = 'instagram'
            
        db.commit()
        
    # Create Session Token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    # Redirect to Dashboard
    redirect_url = utils.get_dashboard_url(user.role)
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response
