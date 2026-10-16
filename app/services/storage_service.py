import asyncio
from pathlib import Path, PurePosixPath
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class StorageError(Exception):
    """Raised when a storage operation fails."""


def generate_storage_key(
    file_type: str,
    project_id: int,
    filename: str,
) -> str:
    """Generate a unique storage key without trusting uploaded paths."""
    safe_filename = filename.replace("\\", "/").split("/")[-1]

    if not safe_filename or safe_filename in {".", ".."}:
        raise ValueError("Invalid filename.")

    return str(
        PurePosixPath(file_type) / str(project_id) / str(uuid4()) / safe_filename
    )


class StorageService:
    def __init__(self) -> None:
        self.backend = settings.storage_backend
        self.bucket = settings.s3_bucket_name
        self.region = settings.aws_region

    def _s3_client(self):
        return boto3.client("s3", region_name=self.region)

    async def save(self, key: str, content: bytes) -> str:
        """Save bytes and return a persistent storage reference."""
        if self.backend == "local":
            path = Path("uploads") / Path(*PurePosixPath(key).parts)
            await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(path.write_bytes, content)
            return str(path)

        if not self.bucket:
            raise StorageError("S3_BUCKET_NAME is not configured.")

        try:
            await asyncio.to_thread(
                self._s3_client().put_object,
                Bucket=self.bucket,
                Key=key,
                Body=content,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("S3 upload failed.") from exc

        return f"s3://{self.bucket}/{key}"

    async def read(self, reference: str) -> bytes:
        """Read bytes from a local path or an S3 reference."""
        if not reference.startswith("s3://"):
            try:
                return await asyncio.to_thread(Path(reference).read_bytes)
            except OSError as exc:
                raise StorageError("Local file read failed.") from exc

        bucket, key = self._parse_s3_reference(reference)

        try:
            response = await asyncio.to_thread(
                self._s3_client().get_object,
                Bucket=bucket,
                Key=key,
            )
            return await asyncio.to_thread(response["Body"].read)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise StorageError("S3 file read failed.") from exc

    async def delete(self, reference: str) -> None:
        """Delete a file from local storage or S3."""
        if not reference.startswith("s3://"):
            try:
                await asyncio.to_thread(
                    Path(reference).unlink,
                    missing_ok=True,
                )
            except OSError as exc:
                raise StorageError("Local file deletion failed.") from exc
            return

        bucket, key = self._parse_s3_reference(reference)

        try:
            await asyncio.to_thread(
                self._s3_client().delete_object,
                Bucket=bucket,
                Key=key,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("S3 file deletion failed.") from exc

    @staticmethod
    def _parse_s3_reference(reference: str) -> tuple[str, str]:
        location = reference.removeprefix("s3://")
        bucket, separator, key = location.partition("/")

        if not separator or not bucket or not key:
            raise StorageError("Invalid S3 storage reference.")

        return bucket, key


storage_service = StorageService()
