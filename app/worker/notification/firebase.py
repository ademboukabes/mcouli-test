from __future__ import annotations
from typing import cast

import firebase_admin # pyright: ignore[reportMissingTypeStubs]
from firebase_admin import credentials, messaging  # pyright: ignore[reportMissingTypeStubs]

from app.core.config import settings
from app.core.logger import logger
from app.schema.notification import UnifiedNotification


INVALID_TOKEN_CODES = {
    "messaging/registration-token-not-registered",
    "messaging/invalid-registration-token",
}


class _SendResponse:
    success: bool
    exception: Exception | None


class _BatchResponse:
    responses: list[_SendResponse]
    

class NotificationDeliveryError(Exception):
    def __init__(
        self,
        *,
        failed_tokens: list[str],
        invalid_tokens: list[str],
    ) -> None:
        self.failed_tokens = failed_tokens
        self.invalid_tokens = invalid_tokens
        super().__init__(
            f"Failed tokens: {failed_tokens}, invalid tokens: {invalid_tokens}"
        )


def init_firebase_app(credentials_path: str | None = None) -> None:
    if firebase_admin._apps: # type: ignore
        return
    if credentials_path is None:
        credentials_path = settings.FIREBASE_CREDENTIALS_PATH
    if credentials_path:
        cred = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(cred) # type: ignore
        logger.info("Firebase initialized with credentials from %s", credentials_path)
        return
    firebase_admin.initialize_app() # type: ignore
    logger.info("Firebase initialized with default credentials")


def _classify_token_failure(error: Exception) -> bool:
    code = getattr(error, "code", None)

    if code in INVALID_TOKEN_CODES:
        return True

    name = error.__class__.__name__
    return name in {"UnregisteredError", "InvalidArgumentError"}


def send_notification(notification: UnifiedNotification) -> None:
    if not notification.tokens:
        logger.debug("Skipping notification without tokens: %s", notification)
        return
    multicast = messaging.MulticastMessage(
        tokens=notification.tokens,
        notification=messaging.Notification(
            title=notification.title,
            body=notification.body,
        ),
        data=notification.data or None,
    )
    response = cast(
    _BatchResponse,
    messaging.send_multicast(multicast) # type: ignore
)

    failed_tokens: list[str] = []
    invalid_tokens: list[str] = []

    for token, result in zip(notification.tokens, response.responses):
        if result.success or result.exception is None:
            continue
        if _classify_token_failure(result.exception):
            invalid_tokens.append(token)
        else:
            failed_tokens.append(token)

    if failed_tokens or invalid_tokens:
        raise NotificationDeliveryError(
            failed_tokens=failed_tokens,
            invalid_tokens=invalid_tokens,
        )

    logger.info(
        "Notification delivered to %d tokens", len(notification.tokens)
    )
