from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.services.storage_service import (
    StorageError,
    StorageService,
    generate_storage_key,
)


def test_generate_storage_key():
    key = generate_storage_key(
        file_type="vcf",
        project_id=12,
        filename="sample.vcf",
    )

    assert key.startswith("vcf/12/")
    assert key.endswith("/sample.vcf")


def test_generate_storage_key_sanitizes_filename():
    key = generate_storage_key(
        file_type="vcf",
        project_id=12,
        filename="../../sample.vcf",
    )

    assert key.endswith("/sample.vcf")
    assert ".." not in key


@pytest.mark.asyncio
async def test_s3_save():
    storage = StorageService()
    storage.backend = "s3"
    storage.bucket = "test-bucket"

    mock_client = MagicMock()

    with patch.object(storage, "_s3_client", return_value=mock_client):
        reference = await storage.save(
            "vcf/12/sample.vcf",
            b"VCF content",
        )

    assert reference == "s3://test-bucket/vcf/12/sample.vcf"

    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="vcf/12/sample.vcf",
        Body=b"VCF content",
    )


@pytest.mark.asyncio
async def test_s3_read():
    storage = StorageService()
    storage.backend = "s3"

    mock_client = MagicMock()
    mock_client.get_object.return_value = {
        "Body": BytesIO(b"VCF content"),
    }

    with patch.object(storage, "_s3_client", return_value=mock_client):
        content = await storage.read("s3://test-bucket/vcf/12/sample.vcf")

    assert content == b"VCF content"

    mock_client.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="vcf/12/sample.vcf",
    )


@pytest.mark.asyncio
async def test_s3_delete():
    storage = StorageService()
    storage.backend = "s3"

    mock_client = MagicMock()

    with patch.object(storage, "_s3_client", return_value=mock_client):
        await storage.delete("s3://test-bucket/vcf/12/sample.vcf")

    mock_client.delete_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="vcf/12/sample.vcf",
    )


@pytest.mark.asyncio
async def test_s3_save_without_bucket():
    storage = StorageService()
    storage.backend = "s3"
    storage.bucket = None

    with pytest.raises(
        StorageError,
        match="S3_BUCKET_NAME is not configured",
    ):
        await storage.save(
            "vcf/12/sample.vcf",
            b"VCF content",
        )
