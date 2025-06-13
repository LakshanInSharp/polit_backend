import os
import logging
from uuid import uuid4
from datetime import datetime
from typing import Optional
from io import BytesIO
import boto3
import psycopg2
from psycopg2 import pool
from fastapi import UploadFile


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv() 


#local file path for temporary storage
FILE_PATH = os.getenv("FILE_PATH")  

#concurency connections
MIN_CONN = int(os.getenv("DB_MIN_CONN", 1))
MAX_CONN = int(os.getenv("DB_MAX_CONN", 100))


# Load config from environment variables
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_FOLDER = os.getenv("S3_FOLDER", "uploads")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

MAX_FILE_SIZE_MB = 50




class FileUploader:
    def __init__(self):
        # Initialize S3 client
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

        # Initialize PostgreSQL connection pool
        self.db_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

        # Ensure table exists
        self.create_table_if_not_exists()

    def create_table_if_not_exists(self):
        query = """
        CREATE TABLE IF NOT EXISTS file_uploads (
            id SERIAL PRIMARY KEY,
            file_name TEXT NOT NULL,
            file_url TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size BIGINT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                conn.commit()
        finally:
            self.db_pool.putconn(conn)




    def upload_file_to_s3(self, file_stream,filename,filetype) -> dict:
        # Validate file size
        # contents = BytesIO(file.file.read())
        logger.debug(f"Validating file size for {filename}")
        contents=file_stream
        contents.seek(0, os.SEEK_END)

        file_size = contents.tell()
        file_size_mb = file_size / (1024 * 1024)  # Convert to MB
        contents.seek(0)
        if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"File size exceeds {MAX_FILE_SIZE_MB}MB limit")

        # 
        # Create unique filename
        ext = os.path.splitext(filename)[1]
        base_name = os.path.splitext(filename)[0].replace(" ", "_")
        unique_suffix = uuid4().hex[:8]
        unique_file_name = f"{base_name}_{unique_suffix}{ext}"
        s3_key = f"{S3_FOLDER}/{unique_file_name}"

        logger.info(f"Uploading {unique_file_name} to S3 bucket {S3_BUCKET_NAME} at key {s3_key}")


        logger.debug("file uplooading to s3 bucket")
        # Upload to S3
        self.s3.upload_fileobj(
            contents,
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                "ContentType": filetype,
                
            }
        )

        logger.info("File uploaded successfully to S3")

        # Construct file URL
        file_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"

        

        
        # Save metadata to DB
        conn = self.db_pool.getconn()
        try:
            logger.debug("File uploding to db")
            with conn.cursor() as cur:
                insert_query = """
                INSERT INTO file_uploads (file_name, file_url, file_type, file_size, uploaded_at)
                VALUES (%s, %s, %s, %s, %s)
                """
               
                cur.execute(insert_query, (
                    unique_file_name,
                    file_url,
                    filetype,
                    file_size_mb,
                    datetime.utcnow()
                ))
                conn.commit()
                logger.info("File metadata saved to database")
        finally:
            self.db_pool.putconn(conn)

        logger.info(f"Uploaded {unique_file_name} to S3 and saved to DB.")

        return file_url
    



    def save_file_to_local_storage(self, file_stream, file_name):
        
        # Create a safe and unique file name
        base_name = os.path.splitext(file_name)[0].replace(" ", "_")
        unique_suffix = uuid4().hex[:8]  # Optional: prevent collisions
        safe_file_name = f"{base_name}_{unique_suffix}.pdf"


        # Define permanent storage path
        storage_dir = os.path.join(FILE_PATH, "pdfs")  # or use full path: /app/static/pdfs
        os.makedirs(storage_dir, exist_ok=True)
        file_path = os.path.join(storage_dir, safe_file_name)

        # logger.info(f"Storing PDF at: {file_path}")

        # Save the uploaded file permanently
        with open(file_path, "wb") as f:
            file_stream.seek(0)
            f.write(file_stream.read())

        return file_path
    


    def delete_file_from_s3(self,filename: str) -> bool:
        """
        Deletes a file from the S3 bucket.
        Parameters:
            filename (str): The exact filename saved in S3 (including folder path if any).
        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        try:
            # Compose the S3 key
            s3_key = f"{S3_FOLDER}/{filename}"
            logger.info(f"Attempting to delete {s3_key} from bucket {S3_BUCKET_NAME}")
            # Delete the object
            self.s3.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            logger.info(f"Successfully deleted {s3_key} from S3")
            return True
        except Exception as e:
            logger.error(f"Error deleting {filename} from S3: {e}")
            return False


    



