

import os
from uuid import uuid4


class DocumentHandler:
    def __init__(self):
        pass

    def get_document(self):
        return self.document

    def set_document(self, document):
        self.document = document


    def save_file_to_local_storage(self, file_stream, file_name):
        
        # Create a safe and unique file name
        base_name = os.path.splitext(file_name)[0].replace(" ", "_")
        unique_suffix = uuid4().hex[:8]  # Optional: prevent collisions
        safe_file_name = f"{base_name}_{unique_suffix}.pdf"


        # Define permanent storage path
        storage_dir = os.path.join(r"D:\INSHARP PROJECTS\POLIT\Polit_AI_Backend\static", "pdfs")  # or use full path: /app/static/pdfs
        os.makedirs(storage_dir, exist_ok=True)
        file_path = os.path.join(storage_dir, safe_file_name)

        # logger.info(f"Storing PDF at: {file_path}")

        # Save the uploaded file permanently
        with open(file_path, "wb") as f:
            file_stream.seek(0)
            f.write(file_stream.read())

        return file_path
    
    def store_file_metadata_to_db():
        pass