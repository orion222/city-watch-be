import logging
import os
import uuid
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

logger = logging.getLogger(__name__)

DIRECTORY = "incidents/"  # Directory in S3 bucket to store images


@lru_cache(maxsize=1)
def get_s3_client():
    """
    Returns a cached S3 client using boto3. The client is configured with the endpoint URL,
    access key, secret key, and region name from environment variables.
    """

    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region_name = os.getenv("AWS_REGION", "us-east-1")

    client_kwargs = {
        "service_name": "s3",
        "region_name": region_name,
        "config": Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    }

    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url

    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key

    return boto3.client(**client_kwargs)


def upload_image_to_s3(file_bytes: bytes, content_type: str = "image/jpeg") -> str:
    """Uploads an image to S3 and returns the public URL.
    Generates random UUID for the filename to avoid collisions.
    Image is stored in the 'incidents/' folder in the bucket.
    """

    bucket_name = os.getenv("AWS_BUCKET_NAME", "city-watch-reports")
    endpoint_url = os.getenv("AWS_ENDPOINT_URL", "http://localhost:9000")
    public_url_base = os.getenv("AWS_PUBLIC_URL_BASE")

    prefix = DIRECTORY.strip("/")
    unique_key = f"{prefix}/{uuid.uuid4().hex}.jpg" if prefix else f"{uuid.uuid4().hex}.jpg"
    client = get_s3_client()

    # 3. Send the file over the network to MinIO
    try:
        client.put_object(
            Bucket=bucket_name,
            Key=unique_key,
            Body=file_bytes,
            ContentType=content_type,
        )
    except (ClientError, BotoCoreError) as e:
        logger.error(f"S3 upload failed for key {unique_key}: {e}")
        raise HTTPException(
            status_code=502,
            detail="Failed to upload image to storage service.",
        ) from e

    if public_url_base:
        return f"{public_url_base.rstrip('/')}/{unique_key}"
    return f"{endpoint_url.rstrip('/')}/{bucket_name}/{unique_key}"
