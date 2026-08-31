import asyncio

from app.core.config import settings
from app.core.logger import logger
from app.infra.database import engine
from app.service.staged_upload_storage import StagedUploadStorageService
from db.generated import upload_request_photos as upload_request_photo_queries

storage_service = StagedUploadStorageService()


async def run_reconcile_pass() -> None:
    async with engine.begin() as conn:
        querier = upload_request_photo_queries.AsyncQuerier(conn)

        stale_photos = [
            photo
            async for photo in querier.list_stale_pending_transfer_photos(
                dollar_1=str(settings.DIRECT_UPLOAD_STALE_PENDING_MINUTES)
            )
        ]

        if not stale_photos:
            return

        confirmed = 0
        failed = 0
        for photo in stale_photos:
            stat = await storage_service.stat_staging_object(photo.staging_storage_key)
            if stat is not None:
                await querier.confirm_upload_request_photo_transfer(
                    id=photo.id,
                    size_bytes=stat.size,
                    mime_type=stat.content_type,
                )
                confirmed += 1
            else:
                await querier.fail_upload_request_photo_transfer(id=photo.id)
                failed += 1

        logger.info(
            "upload_reconciler: reconciled %d stale photo(s) — %d confirmed, %d failed",
            len(stale_photos),
            confirmed,
            failed,
        )


async def main() -> None:
    logger.info(
        "Upload reconciler worker starting, poll_interval=%ds, stale_after=%dmin",
        settings.DIRECT_UPLOAD_RECONCILE_POLL_INTERVAL_SECONDS,
        settings.DIRECT_UPLOAD_STALE_PENDING_MINUTES,
    )
    while True:
        try:
            await run_reconcile_pass()
        except Exception:
            logger.exception("upload_reconciler: pass failed")
        await asyncio.sleep(settings.DIRECT_UPLOAD_RECONCILE_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
