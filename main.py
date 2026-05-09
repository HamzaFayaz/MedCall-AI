import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.logger import logger

app = FastAPI(title="Voice Agent System")

# Mount the static client files
app.mount("/client", StaticFiles(directory="client", html=True), name="client")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    logger.info("Starting up the Voice Agent Server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
