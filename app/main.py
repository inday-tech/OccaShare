from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .db.database import engine, Base
from .routers import website, auth, admin, bookings, oauth, caterers, caterer_dashboard, customer_dashboard, verification
from .db import models

# Create tables
Base.metadata.create_all(bind=engine)

from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# Add SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key="your-secret-key") # Replace with env var in prod

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(website.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(bookings.router)
app.include_router(oauth.router)
app.include_router(caterers.router)

app.include_router(caterer_dashboard.router)
app.include_router(customer_dashboard.router)
app.include_router(verification.router)

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
