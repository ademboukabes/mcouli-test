import asyncio
import json

from app.core.config import settings
from app.core.logger import logger
from app.infra.nats import NatsClient
from app.infra.email import EmailSender


async def handle_message(raw_payload: bytes | str) -> None:
    try:
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode()

        payload = json.loads(raw_payload)
        email = payload.get("email")
        otp = payload.get("otp")

        if not email or not otp:
            logger.error("Invalid email.send_otp payload: %s", raw_payload)
            return

        success = await EmailSender.send_otp_email(to_email=email, otp=otp)
        if success:
            logger.info("Successfully sent OTP email to %s", email)
        else:
            logger.error("Failed to send OTP email to %s", email)

    except Exception:
        logger.exception("Unexpected error in email worker")


async def run_worker() -> None:
    logger.info("Email worker started")

    async def wrapped_handler(msg: bytes | str) -> None:
        await handle_message(msg)

    # Subscribe to the email.send_otp subject
    await NatsClient.subscribe("email.send_otp", wrapped_handler)

    # Keep the worker running
    await asyncio.Event().wait()


async def main() -> None:
    await NatsClient.connect(
        host=settings.NATS_HOST,
        port=settings.NATS_PORT,
        user=settings.NATS_USER,
        password=settings.NATS_PASSWORD,
    )

    try:
        await run_worker()
    finally:
        await NatsClient.close()
        logger.info("Email Worker shutdown")


if __name__ == "__main__":
    asyncio.run(main())
