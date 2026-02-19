from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..db import crud, schemas, database

router = APIRouter(prefix="/contact", tags=["contact"])
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def get_contact_page(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

@router.post("/", response_class=HTMLResponse)
async def submit_contact_form(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(database.get_db)
):
    inquiry_data = schemas.InquiryCreate(name=name, email=email, message=message)
    crud.create_inquiry(db, inquiry_data)
    
    return templates.TemplateResponse("contact.html", {
        "request": request, 
        "success_message": "Thank you for your inquiry! We will get back to you soon."
    })
