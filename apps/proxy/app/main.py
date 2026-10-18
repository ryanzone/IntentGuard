from fastapi import FastAPI
from app.api.routes import router as api_router
from app.api.escalation import router as escalation_router

app = FastAPI(
    title="PayPal IntentGuard Proxy",
    description="Agentic Intent Verification Gateway for PayPal API",
    version="1.0.0"
)

app.include_router(api_router)
app.include_router(escalation_router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "paypal-intentguard-proxy"}