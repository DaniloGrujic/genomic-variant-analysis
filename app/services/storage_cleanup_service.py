import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pending_storage_deletion import PendingStorageDeletion
from app.services.storage_service import StorageError, storage_service

logger = logging.getLogger(__name__)


async def process_pending_deletions(
    db: AsyncSession,
    limit: int = 100,
    deletion_id: int | None = None,
) -> tuple[int, int]:
    """Process pending storage deletions.

    Returns:
        A tuple containing (successful_deletions, failed_deletions).
    """
    query = select(PendingStorageDeletion)

    if deletion_id is not None:
        query = query.where(PendingStorageDeletion.id == deletion_id)

    elif storage_service.backend == "s3":
        if not storage_service.bucket:
            logger.warning("S3 cleanup skipped: no bucket configured")
            return 0, 0

        expected_prefix = f"s3://{storage_service.bucket}/"

        query = query.where(
            PendingStorageDeletion.storage_reference.startswith(expected_prefix)
        )

    elif storage_service.backend == "local":
        query = query.where(
            not_(PendingStorageDeletion.storage_reference.startswith("s3://"))
        )

    # Select only deletions whose retry delay has elapsed.
    now = datetime.now(timezone.utc)

    retry_minutes = [
        2 ** (attempt - 1) if attempt <= 6 else 60 for attempt in range(1, 8)
    ]

    retry_conditions = [
        PendingStorageDeletion.attempts == 0,
        PendingStorageDeletion.last_attempt_at.is_(None),
    ]

    for attempt, minutes in enumerate(retry_minutes, start=1):
        retry_conditions.append(
            and_(
                PendingStorageDeletion.attempts == attempt,
                PendingStorageDeletion.last_attempt_at
                <= now - timedelta(minutes=minutes),
            )
        )

    # Handle attempts beyond the explicitly enumerated retry delays.
    retry_conditions.append(
        and_(
            PendingStorageDeletion.attempts > 7,
            PendingStorageDeletion.last_attempt_at <= now - timedelta(minutes=60),
        )
    )

    # Apply retry eligibility before ordering and limiting.
    query = query.where(or_(*retry_conditions))

    query = query.order_by(
        PendingStorageDeletion.created_at,
        PendingStorageDeletion.id,
    ).limit(limit)

    result = await db.execute(query)
    pending_deletions = result.scalars().all()

    successful = 0
    failed = 0

    for deletion in pending_deletions:
        if deletion.attempts > 0 and deletion.last_attempt_at is not None:
            retry_delay = timedelta(minutes=min(2 ** (deletion.attempts - 1), 60))

            next_retry_at = deletion.last_attempt_at + retry_delay

            if datetime.now(timezone.utc) < next_retry_at:
                logger.debug(
                    "Skipping deletion %s: retry not due until %s",
                    deletion.id,
                    next_retry_at,
                )
                continue
        reference = deletion.storage_reference

        # Only process references compatible with the active backend.
        is_s3_reference = reference.startswith("s3://")

        if storage_service.backend == "local" and is_s3_reference:
            logger.warning(
                "Skipping S3 deletion %s: active backend is local",
                reference,
            )
            continue

        if storage_service.backend == "s3" and not is_s3_reference:
            logger.warning(
                "Skipping local deletion %s: active backend is S3",
                reference,
            )
            continue

        if is_s3_reference:
            expected_prefix = f"s3://{storage_service.bucket}/"

            if not storage_service.bucket or not reference.startswith(expected_prefix):
                logger.warning(
                    "Skipping S3 deletion %s: reference does not match "
                    "the configured bucket",
                    reference,
                )
                continue

        try:
            await storage_service.delete(reference)

        except StorageError as exc:
            deletion.attempts += 1
            deletion.last_error = str(exc)
            deletion.last_attempt_at = datetime.now(timezone.utc)

            await db.commit()

            logger.warning(
                "Storage deletion failed for %s (attempt %s): %s",
                deletion.storage_reference,
                deletion.attempts,
                exc,
            )

            failed += 1

        else:
            await db.delete(deletion)
            await db.commit()

            successful += 1

    return successful, failed
