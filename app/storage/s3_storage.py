"""S3 storage backend for cloud deployments."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json


class S3Storage:
    """S3-compatible storage backend."""
    
    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """
        Initialize S3 storage.
        
        Args:
            bucket: S3 bucket name
            region: AWS region
            endpoint_url: Custom endpoint URL (for S3-compatible services)
            access_key: AWS access key
            secret_key: AWS secret key
        """
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        
        # Initialize boto3 client
        try:
            import boto3
            
            self.s3_client = boto3.client(
                "s3",
                region_name=region,
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key or os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=secret_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
        except ImportError:
            raise RuntimeError(
                "boto3 not installed. Install with: pip install boto3"
            )
    
    def save_psd(self, job_id: str, psd_bytes: bytes) -> str:
        """
        Save PSD file to S3.
        
        Args:
            job_id: Job ID
            psd_bytes: PSD file bytes
            
        Returns:
            S3 object key
        """
        key = f"{job_id}/output.psd"
        
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=psd_bytes,
            ContentType="image/vnd.adobe.photoshop",
        )
        
        return key
    
    def save_preview(self, job_id: str, layer_name: str, png_bytes: bytes) -> str:
        """
        Save preview PNG to S3.
        
        Args:
            job_id: Job ID
            layer_name: Layer name
            png_bytes: PNG file bytes
            
        Returns:
            S3 object key
        """
        key = f"{job_id}/preview_{layer_name}.png"
        
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=png_bytes,
            ContentType="image/png",
        )
        
        return key
    
    def save_metadata(self, job_id: str, metadata: Dict[str, Any]) -> str:
        """
        Save metadata JSON to S3.
        
        Args:
            job_id: Job ID
            metadata: Metadata dictionary
            
        Returns:
            S3 object key
        """
        key = f"{job_id}/metadata.json"
        
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(metadata, default=str),
            ContentType="application/json",
        )
        
        return key
    
    def get_signed_url(
        self,
        key: str,
        expiration_seconds: int = 3600,
    ) -> str:
        """
        Get signed URL for S3 object.
        
        Args:
            key: S3 object key
            expiration_seconds: URL expiration time in seconds
            
        Returns:
            Signed URL
        """
        url = self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expiration_seconds,
        )
        
        return url
    
    def cleanup_job(self, job_id: str) -> None:
        """
        Clean up job files from S3.
        
        Args:
            job_id: Job ID
        """
        # List all objects with job_id prefix
        response = self.s3_client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=f"{job_id}/",
        )
        
        # Delete all objects
        if "Contents" in response:
            for obj in response["Contents"]:
                self.s3_client.delete_object(
                    Bucket=self.bucket,
                    Key=obj["Key"],
                )


def get_s3_storage() -> S3Storage:
    """Get S3 storage instance."""
    from app.core.config import settings
    
    return S3Storage(
        bucket=getattr(settings, "S3_BUCKET", "psdfy"),
        region=getattr(settings, "S3_REGION", "us-east-1"),
        endpoint_url=getattr(settings, "S3_ENDPOINT_URL", None),
    )
