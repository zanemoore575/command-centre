from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import engine, Base
from app.api import health, journal, chat_agentic

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Command Centre API",
    description="Personal AI system for tracking the CAiS business journey",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(journal.router, prefix="/api/journal", tags=["journal"])
app.include_router(chat_agentic.router)  # New agentic chat with file upload support


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Command Centre API",
        "version": "0.1.0",
        "docs": "/docs"
    }
