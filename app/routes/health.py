from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "healthy", "version": "1.0.0"}
