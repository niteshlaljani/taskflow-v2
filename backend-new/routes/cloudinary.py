import time
import cloudinary
import cloudinary.utils
from fastapi import APIRouter, HTTPException, Depends, Query
from helpers import get_current_user
from config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

router = APIRouter(prefix="/api", tags=["cloudinary"])


@router.get("/cloudinary/signature")
async def cloudinary_signature(
    user: dict = Depends(get_current_user),
    folder: str = Query("taskflow/attachments"),
    resource_type: str = Query("auto", pattern="^(image|video|raw|auto)$"),
):
    if not folder.startswith("taskflow/"):
        raise HTTPException(400, "Invalid folder")
    timestamp = int(time.time())
    params = {"timestamp": timestamp, "folder": folder}
    signature = cloudinary.utils.api_sign_request(params, CLOUDINARY_API_SECRET)
    return {
        "signature": signature,
        "timestamp": timestamp,
        "cloud_name": CLOUDINARY_CLOUD_NAME,
        "api_key": CLOUDINARY_API_KEY,
        "folder": folder,
        "resource_type": resource_type,
    }
