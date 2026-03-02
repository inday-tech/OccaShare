from fastapi import APIRouter, Request, Form, Depends
from jose import JWTError, jwt
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..db import crud, schemas, database, models
from ..core import security as auth, utils

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(database.get_db)):
    token = request.cookies.get("access_token")
    user = None
    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
        try:
            payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
            email: str = payload.get("sub")
            if email:
                user = db.query(models.User).filter(models.User.email == email).first()
        except JWTError:
            pass

    packages = db.query(models.CateringPackage).filter(models.CateringPackage.is_active == True).limit(3).all()
    caterers = db.query(models.CatererProfile).order_by(models.CatererProfile.rating.desc()).limit(5).all()
    highlighted_reviews = db.query(models.Review).filter(models.Review.is_highlighted == True).order_by(models.Review.created_at.desc()).limit(6).all()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "packages": packages,
        "caterers": caterers,
        "highlighted_reviews": highlighted_reviews,
        "user": user
    })

@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@router.get("/support/help-center", response_class=HTMLResponse)
async def help_center_page(request: Request):
    return templates.TemplateResponse("support/help_center.html", {"request": request})

@router.get("/support/privacy-policy", response_class=HTMLResponse)
async def privacy_policy_page(request: Request):
    return templates.TemplateResponse("support/privacy_policy.html", {"request": request})

@router.get("/support/terms-of-service", response_class=HTMLResponse)
async def terms_of_service_page(request: Request):
    return templates.TemplateResponse("support/terms_of_service.html", {"request": request})

@router.get("/how-it-works", response_class=HTMLResponse)
async def how_it_works_page(request: Request):
    return templates.TemplateResponse("how_it_works.html", {"request": request})

@router.get("/event-categories", response_class=HTMLResponse)
async def event_categories_page(request: Request):
    return templates.TemplateResponse("event_categories.html", {"request": request})
