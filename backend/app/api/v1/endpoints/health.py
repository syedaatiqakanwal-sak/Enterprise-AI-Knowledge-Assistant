from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "postgres": "pending",
            "mongodb": "pending",
            "redis": "pending",
            "qdrant": "pending"
        }
    }
