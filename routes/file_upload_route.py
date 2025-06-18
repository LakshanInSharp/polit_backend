from typing import List
from dotenv import load_dotenv
from fastapi import Depends, UploadFile, File, HTTPException, APIRouter
import logging
import io

from sqlalchemy import text
from schemas.resources_schema import Resource
from service import user_service
from service.Document_handler import FileUploader
import httpx
import os
from sqlalchemy.ext.asyncio import AsyncSession
from utils.format_file_size import format_size

load_dotenv()
AI_BACKEND_FILE_UPLOADER_URL = os.getenv("AI_BACKEND_FILE_UPLOADER_URL")
AI_BACKEND_FILE_DELETE_FROM_PINECONE_URL = os.getenv("AI_BACKEND_FILE_DELETE_FROM_PINECONE_URL")

upload_router = APIRouter()
Document_Handler = FileUploader()


@upload_router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    logger = logging.getLogger(__name__)
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file format. Only PDF allowed.")
    
    logger.debug("File upload initiated")
    print(f"Received file: {file.filename}")
    
    file_url = None
    
    try:
        # Read file into memory
        logger.debug("Reading file into memory")
        file_bytes = await file.read()
        file_stream = io.BytesIO(file_bytes)
        file_name = file.filename
        filetype = file.content_type
                
        # Upload file to S3 and save metadata to PostgreSQL
        logger.debug("File Uploading to s3 bucket")
        file_url = Document_Handler.upload_file_to_s3(file_stream, file_name, filetype)
        logger.info(f"File uploaded to S3: {file_url}")
        
    except Exception as e:
        logger.error(f"Error during S3 upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    
    # Notify AI backend - this is separate from file upload
    try:
        ai_backend_url = AI_BACKEND_FILE_UPLOADER_URL
        
        # Increase timeout for AI backend since it takes time
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            logger.debug("Sending request to AI backend...")
            response = await client.post(ai_backend_url, json={"file_path": file_url})
            
            logger.debug(f"AI backend response status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"AI backend failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise HTTPException(status_code=500, detail=error_msg)
            
            logger.info(f"AI backend response: {response.status_code} - {response.text}")
    
    
    except HTTPException:
        # Re-raise our custom HTTPException (from status code check above)
        raise
    except httpx.TimeoutException as timeout_error:
        error_msg = f"AI backend request timed out: {str(timeout_error)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    
    except httpx.RequestError as request_error:
        error_msg = f"Failed to connect to AI backend: {str(request_error)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    
    except Exception as ai_error:
        error_msg = f"Unexpected error while notifying AI backend: {str(ai_error)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    
    # Return success only if both operations succeeded
    return {
        "message": "Successfully uploaded to PostgreSQL and sent to AI backend",
    }



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
            file_size=format_size(row["file_size"] * 1024 * 1024),
            uploaded_at=row["uploaded_at"],
        )
        for row in rows
    ]
    return resources




@upload_router.delete("/delete-resource/{resource_id}")
async def delete_resource(resource_id: int,db: AsyncSession = Depends(user_service.get_db)):
    logger = logging.getLogger(__name__)
    # Step 1: Check if the resource exists and fetch file_name
    fetch_sql = text("SELECT file_name FROM file_uploads WHERE id = :id")
    result = await db.execute(fetch_sql, {"id": resource_id})
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    logger.info(row)
    logger.debug("get file name from database")
    filename = row[0]  # file_name from DB

    # Generate the full S3 key
    logger.info(f"sucessffully get it{filename}")


    # Step 2: Delete from S3
    s3_deleted = Document_Handler.delete_file_from_s3( filename)
    if not s3_deleted:
        raise HTTPException(status_code=500, detail="Failed to delete file from S3")
    

    # Step 3: Delete from database
    delete_sql = text("DELETE FROM file_uploads WHERE id = :id")
    await db.execute(delete_sql, {"id": resource_id})
    await db.commit()
    

    #delete from pinecone
    try:
        ai_backend_url =AI_BACKEND_FILE_DELETE_FROM_PINECONE_URL 
        print(ai_backend_url)       
        async with httpx.AsyncClient() as client:
                logger.info("Deleting from AI backend-{resource_id}")
                response = await client.post(ai_backend_url, json={"file_path": filename})
                logger.info(f"AI backend response: {response.status_code} - {response.text}")


    except Exception as e:
        logger.error(f"Failed to delete from Pinecone: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete from Pinecone")


    return {"message": f"Resource with ID {resource_id} deleted successfully"}