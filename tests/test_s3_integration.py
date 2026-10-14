from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.annotation_file import AnnotationFile
from app.models.pending_storage_deletion import PendingStorageDeletion
from app.services.storage_cleanup_service import process_pending_deletions
from app.services.storage_service import storage_service

VCF_CONTENT = (
    "##fileformat=VCFv4.2\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    "1\t100\trs123\tA\tG\t150\tPASS\tAF=0.25\n"
)


def test_vcf_upload_to_s3():
    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):
        project_response = client.post(
            "/projects/",
            json={
                "name": "S3 VCF Test",
                "description": "Testing VCF upload with mocked S3",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "sample.vcf",
                    VCF_CONTENT,
                    "text/plain",
                )
            },
        )

        assert upload_response.status_code == 201

        data = upload_response.json()

        assert data["filename"] == "sample.vcf"
        assert data["variant_count"] == 1

        mock_s3.put_object.assert_called_once()

        arguments = mock_s3.put_object.call_args.kwargs

        assert arguments["Bucket"] == "test-bucket"
        assert arguments["Key"].startswith(f"vcf/{project_id}/")
        assert arguments["Key"].endswith("/sample.vcf")
        assert arguments["Body"] == VCF_CONTENT.encode("utf-8")

        vcf_id = data["id"]

        get_response = client.get(f"/projects/{project_id}/vcf/{vcf_id}")

        assert get_response.status_code == 200
        assert get_response.json()["variant_count"] == 1


def test_annotation_workflow_with_s3():
    annotation_content = (
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsingle nucleotide variant\tExample\t7157\tTP53\tPathogenic\t"
        "rs123\t1\t100\t100\tA\tG\n"
    )

    # Simulate S3 object storage using an in-memory dictionary.
    objects = {}
    mock_s3 = MagicMock()

    def put_object(*, Bucket, Key, Body):
        objects[(Bucket, Key)] = Body

    def get_object(*, Bucket, Key):
        return {"Body": BytesIO(objects[(Bucket, Key)])}

    mock_s3.put_object.side_effect = put_object
    mock_s3.get_object.side_effect = get_object

    # Switch storage to S3 without making real AWS requests.
    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):
        # 1. Create a project.
        project_response = client.post(
            "/projects/",
            json={
                "name": "S3 Annotation Workflow",
                "description": "Test S3 annotation retrieval",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        # 2. Upload a VCF file.
        vcf_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "sample.vcf",
                    VCF_CONTENT,
                    "text/plain",
                )
            },
        )

        assert vcf_response.status_code == 201
        vcf_id = vcf_response.json()["id"]

        # 3. Upload a ClinVar annotation file.
        annotation_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "clinvar.tsv",
                    annotation_content,
                    "text/tab-separated-values",
                )
            },
        )

        assert annotation_response.status_code == 201
        assert annotation_response.json()["entry_count"] == 1

        # 4. Run variant annotation.
        analysis_response = client.post(f"/analysis/{vcf_id}/annotate")

        assert analysis_response.status_code == 200

        result = analysis_response.json()

        assert result["vcf_id"] == vcf_id
        assert result["matched_variants"] == 1

        # 5. Confirm that the annotation was retrieved from S3.
        mock_s3.get_object.assert_called_once()

        assert annotation_content.encode("utf-8") in objects.values()

        # 6. Verify that the annotation was saved in PostgreSQL.
        variants_response = client.get(
            f"/analysis/{vcf_id}/variants",
            params={"gene": "TP53"},
        )

        assert variants_response.status_code == 200
        assert variants_response.json()["total"] == 1


def test_delete_vcf_from_s3():
    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):
        # Create a project.
        project_response = client.post(
            "/projects/",
            json={
                "name": "S3 Delete Test",
                "description": "Test queued VCF deletion",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        # Upload a VCF file.
        upload_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "delete_test.vcf",
                    VCF_CONTENT,
                    "text/plain",
                )
            },
        )

        assert upload_response.status_code == 201
        vcf_id = upload_response.json()["id"]

        mock_s3.put_object.assert_called_once()

        storage_reference = (
            f"s3://test-bucket/{mock_s3.put_object.call_args.kwargs['Key']}"
        )

        # Request deletion through FastAPI.
        delete_response = client.delete(f"/projects/{project_id}/vcf/{vcf_id}")

        assert delete_response.status_code == 204

        # S3 deletion is now deferred to the cleanup worker.
        mock_s3.delete_object.assert_not_called()

        # The VCF metadata is immediately removed.
        get_response = client.get(f"/projects/{project_id}/vcf/{vcf_id}")

        assert get_response.status_code == 404

        async def cleanup_test_deletion():
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PendingStorageDeletion).where(
                        PendingStorageDeletion.storage_reference == storage_reference
                    )
                )

                pending = result.scalar_one_or_none()

                if pending is not None:
                    await db.delete(pending)
                    await db.commit()

        client.portal.call(cleanup_test_deletion)


def test_delete_annotation_from_s3():
    annotation_content = (
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsingle nucleotide variant\tExample\t7157\tTP53\tPathogenic\t"
        "rs123\t1\t100\t100\tA\tG\n"
    )

    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):
        # 1. Create a project.
        project_response = client.post(
            "/projects/",
            json={
                "name": "S3 Annotation Delete Test",
                "description": "Test annotation deletion from S3",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        # 2. Upload an annotation file.
        upload_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "clinvar.tsv",
                    annotation_content,
                    "text/tab-separated-values",
                )
            },
        )

        assert upload_response.status_code == 201
        annotation_id = upload_response.json()["id"]

        # 3. Capture the S3 key used during upload.
        mock_s3.put_object.assert_called_once()

        storage_reference = (
            f"s3://test-bucket/{mock_s3.put_object.call_args.kwargs['Key']}"
        )

        # 4. Delete the annotation through FastAPI.
        delete_response = client.delete(
            f"/projects/{project_id}/annotation/{annotation_id}"
        )

        assert delete_response.status_code == 204

        # 5. Verify S3 deletion used the same key.
        mock_s3.delete_object.assert_not_called()

        # 6. Verify the database record was deleted.
        list_response = client.get(f"/projects/{project_id}/annotation/")

        assert list_response.status_code == 200
        assert all(
            annotation["id"] != annotation_id for annotation in list_response.json()
        )

        # Remove the mocked S3 deletion record created by this test.
        async def cleanup_test_deletion():
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PendingStorageDeletion).where(
                        PendingStorageDeletion.storage_reference == storage_reference
                    )
                )

                pending = result.scalar_one_or_none()

                if pending is not None:
                    await db.delete(pending)
                    await db.commit()

        client.portal.call(cleanup_test_deletion)


def test_vcf_s3_cleanup_after_database_failure():
    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):
        # 1. Create a project while the database works normally.
        project_response = client.post(
            "/projects/",
            json={
                "name": "S3 Database Failure Test",
                "description": "Verify cleanup after database failure",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        # 2. Simulate a database failure during VCF upload.
        with (
            patch.object(
                AsyncSession,
                "flush",
                new_callable=AsyncMock,
                side_effect=SQLAlchemyError("Simulated database failure"),
            ),
            pytest.raises(SQLAlchemyError, match="Simulated database failure"),
        ):
            client.post(
                f"/projects/{project_id}/vcf/",
                files={
                    "file": (
                        "failure_test.vcf",
                        VCF_CONTENT,
                        "text/plain",
                    )
                },
            )

        # 3. Confirm the VCF was uploaded to mocked S3.
        mock_s3.put_object.assert_called_once()

        uploaded_key = mock_s3.put_object.call_args.kwargs["Key"]

        # 4. Confirm the uploaded object was cleaned up.
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=uploaded_key,
        )

        # 5. Confirm no VCF metadata was committed.
        response = client.get(f"/projects/{project_id}/vcf/")

        assert response.status_code == 200
        assert response.json() == []


def test_annotation_s3_cleanup_after_database_failure():
    annotation_content = (
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsingle nucleotide variant\tExample\t7157\tTP53\tPathogenic\t"
        "rs123\t1\t100\t100\tA\tG\n"
    )

    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):
        # 1. Create a project before introducing the database failure.
        project_response = client.post(
            "/projects/",
            json={
                "name": "S3 Annotation Failure Test",
                "description": "Verify annotation cleanup after DB failure",
            },
        )

        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        # 2. Simulate a PostgreSQL failure during annotation upload.
        with (
            patch.object(
                AsyncSession,
                "commit",
                new_callable=AsyncMock,
                side_effect=SQLAlchemyError("Simulated database failure"),
            ),
            pytest.raises(
                SQLAlchemyError,
                match="Simulated database failure",
            ),
        ):
            client.post(
                f"/projects/{project_id}/annotation/",
                files={
                    "file": (
                        "failure_test.tsv",
                        annotation_content,
                        "text/tab-separated-values",
                    )
                },
            )

        # 3. Confirm the file was uploaded to mocked S3.
        mock_s3.put_object.assert_called_once()

        uploaded_key = mock_s3.put_object.call_args.kwargs["Key"]

        # 4. Confirm the S3 object was deleted after the DB failure.
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=uploaded_key,
        )

        # 5. Confirm no annotation metadata was committed.
        response = client.get(f"/projects/{project_id}/annotation/")

        assert response.status_code == 200
        assert response.json() == []


def test_vcf_deletion_database_failure():
    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):
        # Create the project.
        project_response = client.post(
            "/projects/",
            json={
                "name": "S3 Deletion Failure Test",
                "description": "Test DB failure during S3 deletion",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        # Upload the VCF.
        upload_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "deletion_failure.vcf",
                    VCF_CONTENT,
                    "text/plain",
                )
            },
        )
        assert upload_response.status_code == 201
        vcf_id = upload_response.json()["id"]

        # Simulate PostgreSQL commit failure during deletion.
        with (
            patch.object(
                AsyncSession,
                "commit",
                new_callable=AsyncMock,
                side_effect=SQLAlchemyError("Simulated deletion failure"),
            ),
            pytest.raises(
                SQLAlchemyError,
                match="Simulated deletion failure",
            ),
        ):
            client.delete(f"/projects/{project_id}/vcf/{vcf_id}")

        # S3 deletion occurred even though the DB commit failed.
        mock_s3.delete_object.assert_not_called()

        # The database record still exists.
        response = client.get(f"/projects/{project_id}/vcf/{vcf_id}")

        assert response.status_code == 200


def test_vcf_pending_storage_deletion_cleanup():
    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):
        # Create a project.
        project_response = client.post(
            "/projects/",
            json={
                "name": "S3 Cleanup Queue Test",
                "description": "Test persistent storage deletion queue",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        # Upload a VCF to mocked S3.
        upload_response = client.post(
            f"/projects/{project_id}/vcf/",
            files={
                "file": (
                    "cleanup_test.vcf",
                    VCF_CONTENT,
                    "text/plain",
                )
            },
        )
        assert upload_response.status_code == 201
        vcf_id = upload_response.json()["id"]

        upload_key = mock_s3.put_object.call_args.kwargs["Key"]
        storage_reference = f"s3://test-bucket/{upload_key}"

        # Delete VCF metadata through the API.
        delete_response = client.delete(f"/projects/{project_id}/vcf/{vcf_id}")
        assert delete_response.status_code == 204

        # Storage deletion must not happen during the API request.
        mock_s3.delete_object.assert_not_called()

        async def verify_and_process_queue():
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PendingStorageDeletion).where(
                        PendingStorageDeletion.storage_reference == storage_reference
                    )
                )
                pending = result.scalar_one()
                pending_id = pending.id

                assert pending.attempts == 0
                assert pending.last_error is None

                # Process only the record created by this test.
                # Other tests may leave unrelated pending records.
                result = await db.execute(
                    select(PendingStorageDeletion).where(
                        PendingStorageDeletion.id == pending_id
                    )
                )
                deletion = result.scalar_one()

                await storage_service.delete(deletion.storage_reference)
                await db.delete(deletion)
                await db.commit()

                remaining = await db.get(PendingStorageDeletion, pending_id)
                assert remaining is None

        client.portal.call(verify_and_process_queue)

        # Verify the exact S3 object was deleted.
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=upload_key,
        )


def test_process_pending_storage_deletions():
    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):

        async def verify_cleanup_service():
            async with AsyncSessionLocal() as db:
                # Create a dedicated queue record.
                deletion = PendingStorageDeletion(
                    storage_reference="s3://test-bucket/test/cleanup-service.vcf",
                )
                db.add(deletion)
                await db.commit()
                await db.refresh(deletion)

                deletion_id = deletion.id

                # Process the pending deletion queue.
                successful, failed = await process_pending_deletions(
                    db,
                    deletion_id=deletion_id,
                )

                assert successful == 1
                assert failed == 0

                # Verify our queue record was removed.
                remaining = await db.get(
                    PendingStorageDeletion,
                    deletion_id,
                )
                assert remaining is None

        client.portal.call(verify_cleanup_service)

        # Verify our S3 object was deleted.
        mock_s3.delete_object.assert_any_call(
            Bucket="test-bucket",
            Key="test/cleanup-service.vcf",
        )


def test_pending_storage_deletion_retry():
    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):

        async def verify_retry():
            async with AsyncSessionLocal() as db:
                # Create a pending deletion.
                deletion = PendingStorageDeletion(
                    storage_reference="s3://test-bucket/test/retry.vcf",
                )
                db.add(deletion)
                await db.commit()
                await db.refresh(deletion)

                deletion_id = deletion.id

                # Simulate a temporary S3 failure.
                mock_s3.delete_object.side_effect = ClientError(
                    {
                        "Error": {
                            "Code": "ServiceUnavailable",
                            "Message": "Temporary S3 failure",
                        }
                    },
                    "DeleteObject",
                )

                successful, failed = await process_pending_deletions(
                    db,
                    deletion_id=deletion_id,
                )

                assert successful == 0
                assert failed == 1

                # Failed deletion must remain in PostgreSQL.
                pending = await db.get(
                    PendingStorageDeletion,
                    deletion_id,
                )

                assert pending is not None
                assert pending.attempts == 1
                assert pending.last_error is not None
                assert pending.last_attempt_at is not None

                # Simulate S3 recovering.
                mock_s3.delete_object.side_effect = None

                # Advance the retry timestamp beyond the one-minute backoff.
                pending.last_attempt_at = datetime.now(timezone.utc) - timedelta(
                    minutes=2
                )
                await db.commit()

                successful, failed = await process_pending_deletions(
                    db,
                    deletion_id=deletion_id,
                )

                assert successful == 1
                assert failed == 0

                # Successful retry removes the queue record.
                remaining = await db.get(
                    PendingStorageDeletion,
                    deletion_id,
                )
                assert remaining is None

        client.portal.call(verify_retry)


def test_annotation_deletion_database_failure():
    annotation_content = (
        "#VariantID\tType\tName\tGeneID\tGeneSymbol\tClinicalSignificance\t"
        "RS_dbSNP\tChromosome\tStart\tStop\tReferenceAllele\tAlternateAllele\n"
        "1\tsingle nucleotide variant\tExample\t7157\tTP53\tPathogenic\t"
        "rs123\t1\t100\t100\tA\tG\n"
    )

    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):
        project_response = client.post(
            "/projects/",
            json={
                "name": "Annotation Rollback Test",
                "description": "Test deletion transaction rollback",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        upload_response = client.post(
            f"/projects/{project_id}/annotation/",
            files={
                "file": (
                    "rollback_test.tsv",
                    annotation_content,
                    "text/tab-separated-values",
                )
            },
        )
        assert upload_response.status_code == 201
        annotation_id = upload_response.json()["id"]

        upload_key = mock_s3.put_object.call_args.kwargs["Key"]
        storage_reference = f"s3://test-bucket/{upload_key}"

        # Simulate PostgreSQL failing during deletion.
        with (
            patch.object(
                AsyncSession,
                "commit",
                new_callable=AsyncMock,
                side_effect=SQLAlchemyError("Simulated database failure"),
            ),
            pytest.raises(SQLAlchemyError),
        ):
            client.delete(f"/projects/{project_id}/annotation/{annotation_id}")

        # The storage object must not be deleted.
        mock_s3.delete_object.assert_not_called()

        # Verify that the annotation and its storage reference
        # remain unchanged and no deletion job was committed.
        async def verify_rollback():
            async with AsyncSessionLocal() as db:
                annotation = await db.get(AnnotationFile, annotation_id)
                assert annotation is not None
                assert annotation.file_path == storage_reference

                result = await db.execute(
                    select(PendingStorageDeletion).where(
                        PendingStorageDeletion.storage_reference == storage_reference
                    )
                )
                assert result.scalar_one_or_none() is None

        client.portal.call(verify_rollback)


def test_cleanup_skips_different_s3_bucket():
    mock_s3 = MagicMock()

    with (
        patch.object(storage_service, "backend", "s3"),
        patch.object(storage_service, "bucket", "test-bucket"),
        patch.object(storage_service, "_s3_client", return_value=mock_s3),
        TestClient(app) as client,
    ):

        async def verify_bucket_protection():
            async with AsyncSessionLocal() as db:
                deletion = PendingStorageDeletion(
                    storage_reference=(
                        "s3://another-bucket/test/should-not-delete.vcf"
                    ),
                )
                db.add(deletion)
                await db.commit()
                await db.refresh(deletion)

                deletion_id = deletion.id

                try:
                    successful, failed = await process_pending_deletions(
                        db,
                        deletion_id=deletion_id,
                    )

                    assert successful == 0
                    assert failed == 0

                    # The record must remain queued.
                    pending = await db.get(
                        PendingStorageDeletion,
                        deletion_id,
                    )

                    assert pending is not None
                    assert pending.attempts == 0
                    assert pending.last_error is None

                    # No S3 operation should have occurred.
                    mock_s3.delete_object.assert_not_called()

                finally:
                    # Remove only the test record.
                    pending = await db.get(
                        PendingStorageDeletion,
                        deletion_id,
                    )

                    if pending is not None:
                        await db.delete(pending)
                        await db.commit()

        client.portal.call(verify_bucket_protection)
