import os
from dotenv import load_dotenv
load_dotenv()

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.logger import logger
from src.gateway.server import webrtc_router

app = FastAPI(title="Voice Agent System")

# Mount the static client files
app.mount("/client", StaticFiles(directory="client", html=True), name="client")

# Include API routers
app.include_router(webrtc_router)

from fastapi.responses import RedirectResponse

@app.get("/")
async def root():
    return RedirectResponse(url="/client/")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    logger.info("Starting up the Voice Agent Server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # pyttsx3 writes comtypes stubs under venv on first speak — must not trigger reload
        reload_excludes=["venv/*", ".venv/*"],
    )
