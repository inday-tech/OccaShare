from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, UploadFile, File, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import shutil
import asyncio
import uuid
import time
from datetime import datetime
from ..db import database, models
from ..core import security as auth
from ..services.verification import verification_service
from ..services.realtime import manager

router = APIRouter(prefix="/customer/verification", tags=["verification"])
templates = Jinja2Templates(directory="templates")

customer_only = auth.RoleChecker(["customer"])

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(client_id)

@router.get("/", response_class=HTMLResponse)
async def verification_page(
    request: Request, 
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    if user.is_verified:
        return RedirectResponse(url="/customer/dashboard?message=already_verified")
    
    return templates.TemplateResponse("customer/verification.html", {
        "request": request,
        "user": user,
        "client_id": f"user_{user.id}_{uuid.uuid4().hex[:8]}"
    })

@router.post("/process")
async def process_verification(
    request: Request,
    client_id: str = Form(...),
    id_document: UploadFile = File(...),
    selfie: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    user: models.User = Depends(customer_only)
):
    # Ensure upload directories
    UPLOAD_DIR = "app/static/uploads/verification"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Save files
    id_ext = os.path.splitext(id_document.filename)[1]
    selfie_ext = os.path.splitext(selfie.filename)[1]
    
    id_filename = f"user_{user.id}_id_{uuid.uuid4()}{id_ext}"
    selfie_filename = f"user_{user.id}_selfie_{uuid.uuid4()}{selfie_ext}"
    
    id_path = os.path.join(UPLOAD_DIR, id_filename)
    selfie_path = os.path.join(UPLOAD_DIR, selfie_filename)
    
    with open(id_path, "wb") as buffer:
        shutil.copyfileobj(id_document.file, buffer)
    with open(selfie_path, "wb") as buffer:
        shutil.copyfileobj(selfie.file, buffer)
        
    id_url = f"/static/uploads/verification/{id_filename}"
    selfie_url = f"/static/uploads/verification/{selfie_filename}"

    # Real-time Simulation
    async def notify(status, message):
        await manager.broadcast_to_client(client_id, {
            "type": "verification_update",
            "status": status,
            "message": message
        })

    await notify("processing", "Extracting ID Data...")
    await asyncio.sleep(1) 
    
    await notify("processing", "Performing OCR...")
    result = verification_service.verify_identity(id_url, selfie_url)
    await asyncio.sleep(1)

    if not result["success"]:
        await notify("error", result["failure_reason"])
        # Log failure
        id_verification = models.IdentityVerification(
            user_id=user.id,
            document_url=id_url,
            selfie_url=selfie_url,
            verification_status="rejected",
            failure_reason=result["failure_reason"]
        )
        db.add(id_verification)
        db.commit()
        
        return templates.TemplateResponse("customer/verification.html", {
            "request": request,
            "user": user,
            "error": result["failure_reason"]
        })

    await notify("processing", "Verifying Face Liveness...")
    await asyncio.sleep(1)

    await notify("processing", "Matching Face with ID...")
    await asyncio.sleep(1)

    # 3. Success -> Update User
    user.is_verified = True
    
    # Create Verification record
    id_verification = models.IdentityVerification(
        user_id=user.id,
        document_url=id_url,
        selfie_url=selfie_url,
        ocr_data=result["ocr_data"],
        verification_status="verified",
        verified_at=datetime.now()
    )
    db.add(id_verification)
    db.commit()
    
    await notify("success", "Identity Verified Successfully!")
    await asyncio.sleep(0.5)
    
    return RedirectResponse(url="/customer/dashboard?success=verified")
