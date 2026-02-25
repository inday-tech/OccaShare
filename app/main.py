from fastapi import FastAPI
import os
from fastapi.staticfiles import StaticFiles
from .db.database import engine, Base
from .routers import website, auth, admin, bookings, social_auth, caterers, packages, caterer_dashboard, customer_dashboard, verification, kyc, quotations, payments, contact
from .db import models

# Create tables
Base.metadata.create_all(bind=engine)

from starlette.middleware.sessions import SessionMiddleware

from .core.config import settings
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

app = FastAPI()

# Add ProxyHeadersMiddleware to handle Ngrok/Proxy headers (X-Forwarded-Proto)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Add SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(website.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(bookings.router)
app.include_router(social_auth.router)
app.include_router(caterers.router)
app.include_router(packages.router)

app.include_router(caterer_dashboard.router)
app.include_router(customer_dashboard.router)
app.include_router(verification.router)
app.include_router(contact.router)
app.include_router(quotations.router)
app.include_router(kyc.router)
app.include_router(payments.router)

from .services.realtime import manager
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            # We just need to keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)
