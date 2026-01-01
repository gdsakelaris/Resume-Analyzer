"""
File storage abstraction layer supporting both local filesystem and AWS S3.

This module provides a unified interface for file operations, allowing seamless
switching between local storage (for development) and S3 (for production).
"""

import os
import uuid
from io import BytesIO
from typing import BinaryIO, Optional
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings


class StorageBackend:
    """Abstract base class for storage backends"""

    def upload_file(self, file: BinaryIO, filename: str) -> str:
        """Upload file and return storage path/URL"""
        raise NotImplementedError

    def download_file(self, file_path: str) -> BytesIO:
        """Download file and return as BytesIO object"""
        raise NotImplementedError

    def delete_file(self, file_path: str) -> bool:
        """Delete file from storage"""
        raise NotImplementedError

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists"""
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """Local filesystem storage backend"""

    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def upload_file(self, file: BinaryIO, filename: str) -> str:
        """Save file to local uploads/ directory"""
        # Generate unique filename to prevent collisions
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(self.base_dir, unique_filename)

        with open(file_path, "wb") as buffer:
            buffer.write(file.read())

        return file_path

    def download_file(self, file_path: str) -> BytesIO:
        """Read file from local filesystem"""
        with open(file_path, "rb") as f:
            return BytesIO(f.read())

    def delete_file(self, file_path: str) -> bool:
        """Delete file from local filesystem"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists on local filesystem"""
        return os.path.exists(file_path)


class S3Storage(StorageBackend):
    """AWS S3 storage backend"""

    def __init__(self):
        self.bucket_name = settings.S3_BUCKET_NAME

        # Initialize S3 client
        # If AWS_ACCESS_KEY_ID is not set, boto3 will use IAM roles (for EC2/ECS)
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
        else:
            # Use IAM roles or instance profile
            self.s3_client = boto3.client('s3', region_name=settings.AWS_REGION)

    def upload_file(self, file: BinaryIO, filename: str) -> str:
        """Upload file to S3 and return S3 key"""
        # Generate unique S3 key with folder structure: resumes/{uuid}_{filename}
        s3_key = f"resumes/{uuid.uuid4()}_{filename}"

        try:
            # Upload file to S3
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': self._get_content_type(filename),
                    'ServerSideEncryption': 'AES256'  # Enable encryption at rest
                }
            )

            # Return S3 URI format: s3://bucket-name/resumes/uuid_filename.pdf
            return f"s3://{self.bucket_name}/{s3_key}"

        except ClientError as e:
            print(f"Error uploading to S3: {e}")
            raise Exception(f"Failed to upload file to S3: {e}")

    def download_file(self, file_path: str) -> BytesIO:
        """Download file from S3 and return as BytesIO"""
        # Parse S3 URI: s3://bucket-name/key
        s3_key = self._parse_s3_uri(file_path)

        try:
            # Download file from S3 into memory
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return BytesIO(response['Body'].read())

        except ClientError as e:
            print(f"Error downloading from S3: {e}")
            raise Exception(f"Failed to download file from S3: {e}")

    def delete_file(self, file_path: str) -> bool:
        """Delete file from S3"""
        s3_key = self._parse_s3_uri(file_path)

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            print(f"Error deleting from S3: {e}")
            return False

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in S3"""
        s3_key = self._parse_s3_uri(file_path)

        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False

    def _parse_s3_uri(self, s3_uri: str) -> str:
        """Parse S3 URI and extract key

        Supports formats:
        - s3://bucket-name/key/path
        - resumes/uuid_filename.pdf (assumes default bucket)
        """
        if s3_uri.startswith("s3://"):
            # Extract key from s3://bucket-name/key format
            parts = s3_uri.replace("s3://", "").split("/", 1)
            if len(parts) == 2:
                return parts[1]
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        else:
            # Assume it's just the key
            return s3_uri

    def _get_content_type(self, filename: str) -> str:
        """Determine content type based on file extension"""
        extension = filename.lower().split('.')[-1]
        content_types = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'doc': 'application/msword',
            'txt': 'text/plain'
        }
        return content_types.get(extension, 'application/octet-stream')


# Storage factory - returns appropriate backend based on settings
def get_storage() -> StorageBackend:
    """Get storage backend based on USE_S3 setting"""
    if settings.USE_S3:
        if not settings.S3_BUCKET_NAME:
            raise ValueError("S3_BUCKET_NAME must be set when USE_S3=True")
        return S3Storage()
    else:
        return LocalStorage()


# Singleton instance
storage = get_storage()
