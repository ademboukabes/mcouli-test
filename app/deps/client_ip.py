from fastapi import Request
from app.core.config import settings


def get_client_ip(request: Request) -> str | None:
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", maxsplit=1)[0].strip() or None

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip() or None

    return request.client.host if request.client else None