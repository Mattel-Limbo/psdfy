"""Async job queue service using Arq."""

import json
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class JobQueue:
    """Async job queue for long-running conversions."""
    
    def __init__(self, redis_url: str = "redis://localhost"):
        """
        Initialize job queue.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.redis = None
        self.queue = None
        
        try:
            import arq
            self.arq_available = True
        except ImportError:
            self.arq_available = False
    
    async def enqueue_conversion(
        self,
        job_id: str,
        file_bytes: bytes,
        mode: str,
        prompt: Optional[str] = None,
        return_previews: bool = False,
        return_metadata: bool = True,
    ) -> str:
        """
        Enqueue a conversion job.
        
        Args:
            job_id: Job ID
            file_bytes: Image file bytes
            mode: Segmentation mode
            prompt: Optional prompt
            return_previews: Whether to return previews
            return_metadata: Whether to return metadata
            
        Returns:
            Job ID
        """
        if not self.arq_available:
            raise RuntimeError(
                "Arq not installed. Install with: pip install arq"
            )
        
        # Create job data
        job_data = {
            "job_id": job_id,
            "file_bytes": file_bytes.hex(),  # Convert to hex for JSON
            "mode": mode,
            "prompt": prompt,
            "return_previews": return_previews,
            "return_metadata": return_metadata,
            "created_at": datetime.now().isoformat(),
            "status": "queued",
        }
        
        # Store in Redis
        import redis
        r = redis.from_url(self.redis_url)
        r.set(f"job:{job_id}", json.dumps(job_data))
        r.lpush("conversion_queue", job_id)
        
        return job_id
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get job status.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job status dictionary
        """
        import redis
        r = redis.from_url(self.redis_url)
        
        job_data = r.get(f"job:{job_id}")
        if not job_data:
            return {"status": "not_found"}
        
        return json.loads(job_data)
    
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: int = 0,
        result: Optional[Dict] = None,
    ) -> None:
        """
        Update job status.
        
        Args:
            job_id: Job ID
            status: Job status (queued, running, completed, failed)
            progress: Progress percentage (0-100)
            result: Result data if completed
        """
        import redis
        r = redis.from_url(self.redis_url)
        
        job_data = json.loads(r.get(f"job:{job_id}") or "{}")
        job_data["status"] = status
        job_data["progress"] = progress
        job_data["updated_at"] = datetime.now().isoformat()
        
        if result:
            job_data["result"] = result
        
        r.set(f"job:{job_id}", json.dumps(job_data))


def get_job_queue() -> JobQueue:
    """Get job queue instance."""
    return JobQueue()
