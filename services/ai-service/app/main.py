from fastapi import FastAPI
app = FastAPI(title="AI Service")

@app.get("/")
def read_root():
    return {"message": "AI Service is running"}
