import logging
import time
from contextlib import asynccontextmanager
import asyncio
from typing import AsyncIterator
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.infra.minio import init_minio_client
from app.infra.nats import NatsClient
from app.infra.redis import RedisClient
from app.router.mobile.auth import router as mobile_auth_router
from app.router.staff.drive import router as staff_drive_router



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("api")



class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:

        start_time = time.time()

        response = await call_next(request)

        process_time = time.time() - start_time

        logger.info(
            "%s %s status=%s time=%.3fs",
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )

        return response


MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await init_minio_client(
                minio_host=settings.MINIO_HOST,
                minio_port=settings.MINIO_API_PORT,
                minio_root_user=settings.MINIO_ROOT_USER,
                minio_root_password=settings.MINIO_ROOT_PASSWORD,
            )
            break
        except Exception as e:
            print(f"[MINIO] Attempt {attempt} failed: {e}")
            if attempt == MAX_RETRIES:
                raise RuntimeError("Cannot connect to MinIO after multiple attempts") from e
            await asyncio.sleep(RETRY_DELAY)

    RedisClient(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
    )

    await NatsClient.connect()

    yield

    await RedisClient.get_instance().close()
    await NatsClient.close()



app = FastAPI(
    title="multAI API",
    description="Mobile and Web API for multAI",
    version="1.0.0",
    lifespan=lifespan,
)



app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/")
def read_root() -> dict[str, str]:
    return {"Hello": "World"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


app.include_router(mobile_auth_router, prefix="/mobile")
app.include_router(staff_drive_router, prefix="/staff")
