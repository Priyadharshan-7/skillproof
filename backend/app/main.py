"""SkillProof - Main FastAPI application.

A project-based career evidence platform with real-time WebSocket synchronization.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
import json
import time
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.services.websocket_manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler initializing DB and resources on startup."""
    from app.database import init_db, SessionLocal
    from app.models import Student
    init_db()
    
    # Auto-seed if database is fresh (great for container & cloud deployments)
    db = SessionLocal()
    try:
        if db.query(Student).count() == 0:
            logger.info("Fresh database detected. Seeding initial demo portfolios...")
            from app.seed import seed_database
            seed_database()
            logger.info("✅ Database seeded successfully.")
    except Exception as e:
        logger.warning(f"Startup seed check: {e}")
    finally:
        db.close()

    logger.info("✅ SkillProof database initialized")
    logger.info("📊 API docs at http://localhost:8000/docs")
    logger.info("⚡ Real-time WebSocket engine ready at /ws")
    yield


app = FastAPI(
    title="SkillProof",
    description="Project-based career evidence platform with real-time sync — show what you can actually do.",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from app.routers import students, github_import, mentors, recruiters
app.include_router(students.router)
app.include_router(github_import.router)
app.include_router(mentors.router)
app.include_router(recruiters.router)

# Serve frontend static assets
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the single-page application frontend."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "SkillProof API is running. Frontend not found at expected path."}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time bi-directional WebSocket connection endpoint."""
    await manager.connect(websocket)
    try:
        while True:
            text_data = await websocket.receive_text()
            try:
                data = json.loads(text_data)
                msg_type = data.get("type", "")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})

                elif msg_type == "simulate_activity":
                    # Allows testing real-time events on demand from client
                    await manager.broadcast({
                        "type": "activity_event",
                        "data": {
                            "title": "Live Verification",
                            "detail": "Prof. Alan Turing approved 'Distributed Consensus' for Marcus Johnson (Score: 92.4)",
                            "badge": "Verified",
                        },
                    })

                elif msg_type == "subscribe":
                    await websocket.send_json({
                        "type": "subscribed",
                        "channel": data.get("channel", "all"),
                    })

            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket client error: {e}")
        await manager.disconnect(websocket)


@app.post("/api/realtime/simulate")
async def trigger_simulated_realtime_event():
    """Trigger a simulated live event for testing WebSocket broadcasts."""
    event = {
        "title": "Mentor Live Verification",
        "detail": "Senior Architect Priya K. verified Docker & FastAPI on 'Cloud Orchestrator'",
        "badge": "Verified",
    }
    await manager.broadcast({
        "type": "activity_event",
        "data": event,
    })
    return {"status": "broadcasted", "event": event, "clients_reached": manager.client_count}


@app.get("/api/health")
async def health_check():
    """Health check endpoint with real-time client metrics."""
    return {
        "status": "ok",
        "service": "SkillProof",
        "realtime_ws_clients": manager.client_count,
    }
