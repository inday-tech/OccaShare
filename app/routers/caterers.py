from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from ..db import database, models, crud
from ..core import security as auth

router = APIRouter(prefix="/caterers", tags=["caterers"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def list_caterers(request: Request, db: Session = Depends(database.get_db)):
    token = request.cookies.get("access_token")
    user = None
    if token:
        try:
            scheme, param = token.split()
            user = auth.verify_token(param, db)
            if user and user.role == "customer":
                return RedirectResponse(url="/customer/marketplace")
        except: pass
    
    caterers = crud.get_caterers(db)
    return templates.TemplateResponse("customer/caterers_list.html", {
        "request": request, 
        "caterers": caterers, 
        "user": user,
        "active_page": "marketplace"
    })

@router.get("/{caterer_id}", response_class=HTMLResponse)
def get_caterer_profile(request: Request, caterer_id: int, db: Session = Depends(database.get_db)):
    token = request.cookies.get("access_token")
    user = None
    if token:
        try:
            scheme, param = token.split()
            user = auth.verify_token(param, db)
        except: pass

    caterer = crud.get_caterer(db, caterer_id=caterer_id)
    if not caterer:
        raise HTTPException(status_code=404, detail="Caterer not found")
    
    return templates.TemplateResponse("caterer/profile.html", {
        "request": request, 
        "caterer": caterer,
        "packages": caterer.packages,
        "gallery_items": caterer.gallery_items,
        "reviews": caterer.reviews,
        "user": user
    })
