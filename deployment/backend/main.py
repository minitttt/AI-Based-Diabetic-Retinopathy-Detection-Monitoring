from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from utils import load_and_preprocess
from inference import predict, load_model
import uvicorn
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading model...")
    load_model()
    yield
    print("Shutting down...")

app = FastAPI(title="DR Detection API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "DR Detection API is running"}

@app.post("/predict")
async def predict_image(file: UploadFile = File(...)):
    contents = await file.read()
    img_np = load_and_preprocess(contents)
    result = predict(img_np)
    
    return {
        "filename": file.filename,
        "prediction": result
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
