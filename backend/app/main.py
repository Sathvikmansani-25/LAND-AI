from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import healthcheck
from app.routes import (
    alert_routes,
    auth_routes,
    bottleneck_routes,
    chatbot_routes,
    heatmap_routes,
    project_routes,
    risk_routes,
    simulate_routes,
)

# Vercel's Python runtime auto-detects a FastAPI instance named `app` at this
# exact path (app/main.py) and deploys the whole thing as one Vercel
# Function -- no vercel.json entrypoint config needed for that part. See
# README's "Deploying to Vercel" section.
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(project_routes.router)
app.include_router(risk_routes.router)
app.include_router(simulate_routes.router)
app.include_router(alert_routes.router)
app.include_router(heatmap_routes.router)
app.include_router(bottleneck_routes.router)
app.include_router(chatbot_routes.router)


@app.get("/api/health")
def health():
    return {"status": "ok" if healthcheck() else "degraded", "app": settings.app_name}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
