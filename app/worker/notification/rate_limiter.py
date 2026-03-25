import asyncio
import time


class RateLimiter:
    def __init__(self, rate: int, per: float) -> None:
        self._rate = rate
        self._per = per
        self._tokens: float = float(rate)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            refill = elapsed * (self._rate / self._per)
            self._tokens = min(self._rate, self._tokens + refill)
            self._last = now

            if self._tokens < 1:
                sleep_time = (1 - self._tokens) * (self._per / self._rate)
                await asyncio.sleep(sleep_time)
                self._tokens = 0
            else:
                self._tokens -= 1
