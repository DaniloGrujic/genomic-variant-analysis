import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.services.storage_cleanup_service import process_pending_deletions

logger = logging.getLogger(__name__)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        successful, failed = await process_pending_deletions(
            db,
            limit=100,
        )

    logger.info(
        "Storage cleanup completed: %s successful, %s failed",
        successful,
        failed,
    )

    print(f"Storage cleanup completed: {successful} successful, {failed} failed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
