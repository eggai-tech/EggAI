import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import aioboto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class MinIODocumentMetadata:
    sha256: str
    original_filename: str
    upload_timestamp: datetime
    file_size: int
    mime_type: str
    document_id: str
    

class MinIOClient:
    def __init__(
        self,
        endpoint_url: str = None,
        access_key: str = None,
        secret_key: str = None,
        bucket_name: str = "documents"
    ):
        self.endpoint_url = endpoint_url or os.getenv("MINIO_ENDPOINT_URL", "http://localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "user")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "password")
        self.bucket_name = bucket_name
        self.session = aioboto3.Session()
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
        
    def _get_client(self):
        return self.session.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            use_ssl=False
        )
        
    async def initialize_buckets(self):
        """Create bucket structure if it doesn't exist"""
        async with self._get_client() as s3:
            try:
                await s3.head_bucket(Bucket=self.bucket_name)
                logger.info(f"Bucket {self.bucket_name} already exists")
            except ClientError:
                await s3.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Created bucket {self.bucket_name}")
                
            # Create folder structure by uploading empty objects
            folders = ["inbox/", "processed/", "failed/", "archive/"]
            for folder in folders:
                try:
                    await s3.put_object(
                        Bucket=self.bucket_name,
                        Key=folder,
                        Body=b''
                    )
                except Exception as e:
                    logger.debug(f"Folder {folder} may already exist: {e}")
                    
    async def generate_document_id(self, content: bytes, filename: str) -> str:
        """Generate unique document ID based on content hash"""
        content_hash = hashlib.sha256(content).hexdigest()[:16]
        return f"{Path(filename).stem}_{content_hash}"
        
    async def upload_to_inbox(
        self, 
        filename: str, 
        content: bytes,
        mime_type: str = "application/octet-stream"
    ) -> MinIODocumentMetadata:
        """Upload a document to the inbox folder"""
        file_hash = hashlib.sha256(content).hexdigest()
        document_id = await self.generate_document_id(content, filename)
        
        metadata = MinIODocumentMetadata(
            sha256=file_hash,
            original_filename=filename,
            upload_timestamp=datetime.utcnow(),
            file_size=len(content),
            mime_type=mime_type,
            document_id=document_id
        )
        
        async with self._get_client() as s3:
            await s3.put_object(
                Bucket=self.bucket_name,
                Key=f"inbox/{filename}",
                Body=content,
                Metadata={
                    'sha256': metadata.sha256,
                    'document_id': metadata.document_id,
                    'original_filename': metadata.original_filename,
                    'upload_timestamp': metadata.upload_timestamp.isoformat(),
                    'file_size': str(metadata.file_size),
                    'mime_type': metadata.mime_type
                }
            )
            
        return metadata
        
    async def list_inbox_files(self) -> List[Dict]:
        """List all files in the inbox folder"""
        return await self._list_files_in_folder("inbox/")
        
    async def list_processed_files(self) -> List[Dict]:
        """List all files in the processed folder"""
        return await self._list_files_in_folder("processed/")
        
    async def _list_files_in_folder(self, prefix: str) -> List[Dict]:
        """List all files in a specific folder"""
        files = []
        async with self._get_client() as s3:
            paginator = s3.get_paginator('list_objects_v2')
            async for page in paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter="/"
            ):
                for obj in page.get('Contents', []):
                    # Skip the folder itself
                    if obj['Key'] == prefix:
                        continue
                        
                    # Get object metadata
                    head_response = await s3.head_object(
                        Bucket=self.bucket_name,
                        Key=obj['Key']
                    )
                    
                    files.append({
                        'key': obj['Key'],
                        'filename': Path(obj['Key']).name,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'metadata': head_response.get('Metadata', {})
                    })
                    
        return files
        
    async def move_file(self, source_key: str, destination_folder: str) -> str:
        """Move a file from one folder to another"""
        filename = Path(source_key).name
        dest_key = f"{destination_folder}/{filename}"
        
        async with self._get_client() as s3:
            # Copy to new location
            await s3.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': source_key},
                Key=dest_key
            )
            
            # Delete from original location
            await s3.delete_object(
                Bucket=self.bucket_name,
                Key=source_key
            )
            
        return dest_key
        
    async def download_file(self, key: str) -> Tuple[bytes, Dict]:
        """Download file content and metadata"""
        async with self._get_client() as s3:
            response = await s3.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            content = await response['Body'].read()
            metadata = response.get('Metadata', {})
            
        return content, metadata
        
    async def file_exists_in_processed(self, document_id: str) -> bool:
        """Check if a document with given ID exists in processed folder"""
        async with self._get_client() as s3:
            paginator = s3.get_paginator('list_objects_v2')
            async for page in paginator.paginate(
                Bucket=self.bucket_name,
                Prefix="processed/"
            ):
                for obj in page.get('Contents', []):
                    if obj['Key'] == 'processed/':
                        continue
                        
                    head_response = await s3.head_object(
                        Bucket=self.bucket_name,
                        Key=obj['Key']
                    )
                    
                    metadata = head_response.get('Metadata', {})
                    if metadata.get('document_id') == document_id:
                        return True
                        
        return False
        
    async def add_error_metadata(self, key: str, error: str):
        """Add error metadata to a file in the failed folder"""
        async with self._get_client() as s3:
            # Get existing object
            response = await s3.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            metadata = response.get('Metadata', {})
            metadata['error'] = error[:1024]  # S3 metadata value limit
            metadata['failed_timestamp'] = datetime.utcnow().isoformat()
            
            # Copy object with new metadata
            await s3.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': key},
                Key=key,
                Metadata=metadata,
                MetadataDirective='REPLACE'
            )