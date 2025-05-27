from typing import List
from dotenv import load_dotenv
from fastapi import Depends, UploadFile, File, HTTPException, APIRouter
import logging
import io
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from service import user_service
from schemas.resources_schema import Resource
from service.Document_handler import FileUploader, format_size
import httpx
import os


load_dotenv()
AI_BACKEND_FILE_UPLOADER_URL = os.getenv("AI_BACKEND_FILE_UPLOADER_URL")

upload_router = APIRouter()
Document_Handler = FileUploader()


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
        file_name = file.filename
        filetype=file.content_type


      

        # Save file locally
        # file_path = Document_Handler.save_file_to_local_storage(file_stream, file.filename)
        # logger.info(f"Saved file to local path: {file_path}")
        
        # Upload file to S3 and save metadata to PostgreSQL
        logger.debug("File Uploading to s3 bucket")
        file_url= Document_Handler.upload_file_to_s3(file_stream, file_name,filetype)
        logger.info(f"File uploaded to S3: {file_url}")



      # Asynchronously notify AI backend
        try:
            ai_backend_url = AI_BACKEND_FILE_UPLOADER_URL      
            async with httpx.AsyncClient() as client:
                response = await client.post(ai_backend_url, json={"file_path": file_url})
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
    



@upload_router.get("/get-resources", response_model=List[Resource])
async def list_resources(db: AsyncSession = Depends(user_service.get_db)) -> List[Resource]:
    raw_sql = text("""
        SELECT id, file_name, file_type, file_size, uploaded_at
        FROM file_uploads
        ORDER BY uploaded_at DESC
    """)

    result = await db.execute(raw_sql)
    rows = result.mappings().all()

    resources = [
        Resource(
            id=row["id"],
            file_name=row["file_name"],
            file_type=row["file_type"],
            file_size=format_size(row["file_size"]),
            uploaded_at=row["uploaded_at"],
        )
        for row in rows
    ]

    return resources
