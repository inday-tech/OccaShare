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
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "packages": packages,
        "caterers": caterers,
        "user": user
    })

@router.post("/contact", response_class=HTMLResponse)
async def submit_contact_form(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(database.get_db)
):
    inquiry_data = schemas.InquiryCreate(name=name, email=email, message=message)
    crud.create_inquiry(db, inquiry_data)
    packages = db.query(models.CateringPackage).filter(models.CateringPackage.is_active == True).limit(3).all()
    caterers = db.query(models.CatererProfile).order_by(models.CatererProfile.rating.desc()).limit(5).all()
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "packages": packages, 
        "caterers": caterers,
        "success_message": "Thank you for your inquiry! We will get back to you soon."
    })
