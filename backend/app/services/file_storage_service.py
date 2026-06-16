"""
File storage service for saving and managing uploaded files
"""
import os
import uuid
from pathlib import Path
from typing import Tuple
from datetime import datetime

class FileStorageService:
    """Service for storing uploaded files"""

    def __init__(self):
        self.base_upload_dir = Path(__file__).parent.parent.parent / "uploads"
        self.base_upload_dir.mkdir(exist_ok=True)

    def save_file(self, file_content: bytes, filename: str, file_type: str) -> Tuple[str, str]:
        """
        Save uploaded file to disk.

        Args:
            file_content: File bytes
            filename: Original filename
            file_type: MIME type (e.g., 'image/jpeg', 'application/pdf')

        Returns:
            Tuple of (file_path, stored_filename)
        """
        # Determine subdirectory based on file type
        if file_type.startswith("image/"):
            subdir = "images"
        elif file_type == "application/pdf":
            subdir = "documents"
        else:
            subdir = "other"

        # Create subdirectory if it doesn't exist
        target_dir = self.base_upload_dir / subdir
        target_dir.mkdir(exist_ok=True)

        # Generate unique filename to avoid conflicts
        file_ext = Path(filename).suffix
        unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{file_ext}"

        # Full path
        file_path = target_dir / unique_filename

        # Write file
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Return relative path from uploads directory
        relative_path = f"{subdir}/{unique_filename}"
        return str(relative_path), unique_filename

    def get_file_path(self, relative_path: str) -> Path:
        """Get absolute path from relative path"""
        return self.base_upload_dir / relative_path

    def file_exists(self, relative_path: str) -> bool:
        """Check if file exists"""
        return self.get_file_path(relative_path).exists()

    def delete_file(self, relative_path: str) -> bool:
        """Delete a file"""
        file_path = self.get_file_path(relative_path)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
