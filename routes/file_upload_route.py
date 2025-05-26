from typing import List
from fastapi import UploadFile, File, HTTPException, APIRouter
import logging
import io
from schemas.resources_schema import Resource
from service.Document_handler import DocumentHandler
import httpx

upload_router = APIRouter()
Document_Handler = DocumentHandler()


dummy_resources = [
    {
        "id": 1,
        "name": "User Guide",
        "type": "PDF",
        "size": "2MB",
        "date_uploaded": "2024-10-15"
    },
    {
        "id": 2,
        "name": "Product Image",
        "type": "Image",
        "size": "500KB",
        "date_uploaded": "2025-01-20"
    },
    {
        "id": 3,
        "name": "Data Sheet",
        "type": "CSV",
        "size": "150KB",
        "date_uploaded": "2025-03-05"
    }
]



@upload_router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    logger = logging.getLogger(__name__)

    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file format. Only PDF allowed.")

    logger.debug("File upload initiated")
    print(f"Received file: {file.filename}")

    try:
        # Read file into memory
        logger.debug("Reading file into memory")
        file_bytes = await file.read()
        file_stream = io.BytesIO(file_bytes)

        file_size = len(file_bytes)
        print(f"File stream size: {file_size} bytes")
        logger.info(f"File size: {file_size} bytes")

        # Save file locally
        file_path = Document_Handler.save_file_to_local_storage(file_stream, file.filename)
        logger.info(f"Saved file to local path: {file_path}")


       # Asynchronously notify AI backend
        try:
            ai_backend_url = "http://localhost:8000/api/process-pdf"  # Change to actual AI backend URL and port
            async with httpx.AsyncClient() as client:
                response = await client.post(ai_backend_url, json={"file_path": file_path})
                logger.info(f"AI backend response: {response.status_code} - {response.text}")
        except Exception as ai_error:
            logger.error(f"Failed to notify AI backend: {str(ai_error)}")
            # You might choose to still return success even if AI backend fails, or raise error.

        # Return response to client
        return {
            "message": "Successfully uploaded to PostgreSQL and sent to AI backend",
            
        }

    except Exception as e:
        logger.error(f"Error during PDF upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    


@upload_router.get("/admin/resources", response_model=List[Resource])
async def get_resources():
    return dummy_resources