from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from models.database import engine, Base
from routes import tank_sensor_routes, tank_config_routes
from services.thingspeak_auto_sync import auto_sync_service
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("🚀 Starting IoT Tank Sensor Monitoring API...")
    logger.info("📊 ThingSpeak Auto-Sync Service initialized")
    logger.info("💡 Use /api/v1/thingspeak/auto-sync/enable and /start to begin automatic data collection")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down IoT Tank Sensor Monitoring API...")
    if auto_sync_service.is_running:
        auto_sync_service.stop()
        logger.info("✅ Auto-sync service stopped")


app = FastAPI(
    title="IoT Tank Sensor Monitoring API",
    description="FastAPI backend for monitoring tank water level sensors and tank configurations with automated ThingSpeak integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tank_sensor_routes.router,
                   prefix="/api/v1", tags=["tank-sensor"])
app.include_router(tank_config_routes.router,
                   prefix="/api/v1", tags=["tank-config"])


@app.get("/")
async def root():
    """API status and auto-sync information"""
    return {
        "message": "IoT Tank Sensor Monitoring API is running!",
        "version": "1.0.0",
        "auto_sync_status": auto_sync_service.get_status(),
        "endpoints": {
            "auto_sync_control": "/api/v1/thingspeak/auto-sync/",
            "tank_config": "/api/v1/tank-config/",
            "tank_sensor": "/api/v1/tank-sensor/",
            "thingspeak": "/api/v1/thingspeak/",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
