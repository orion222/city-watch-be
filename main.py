from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import marker, address, gemini

app = FastAPI(title="HTV Project API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(marker.router)
app.include_router(address.router)
app.include_router(gemini.router)

@app.get("/")
async def root():
    return {"message": "Welcome to HTV Project API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
