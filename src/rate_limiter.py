import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateLimitConfig:
    requests_per_minute: int
    tokens_per_minute: int = 0
    tokens_per_request: int = 0


PROVIDER_LIMITS = {
    "gemini": RateLimitConfig(requests_per_minute=14, tokens_per_minute=1_000_000, tokens_per_request=2000),
    "anthropic": RateLimitConfig(requests_per_minute=50, tokens_per_request=4000),
    "openai": RateLimitConfig(requests_per_minute=100, tokens_per_request=3000),
    "groq": RateLimitConfig(requests_per_minute=28, tokens_per_minute=6000, tokens_per_request=2000),
    "ollama": RateLimitConfig(requests_per_minute=1000),
    "timps-coder": RateLimitConfig(requests_per_minute=1000),
    "mcp_sampler": RateLimitConfig(requests_per_minute=200),
}


class TokenBucket:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
        self._async_lock = asyncio.Lock()
        self._sync_lock = threading.Lock()

    async def acquire(self, count: int = 1, timeout: float = 60.0) -> bool:
        deadline = time.time() + timeout
        while True:
            async with self._async_lock:
                self._refill()
                if self.tokens >= count:
                    self.tokens -= count
                    return True
                deficit = count - self.tokens
                wait_time = deficit / self.rate
            if time.time() + wait_time > deadline:
                return False
            await asyncio.sleep(min(wait_time, 1.0))

    def sync_acquire(self, count: int = 1, timeout: float = 60.0) -> bool:
        deadline = time.time() + timeout
        while True:
            with self._sync_lock:
                self._refill()
                if self.tokens >= count:
                    self.tokens -= count
                    return True
                deficit = count - self.tokens
                wait_time = deficit / self.rate
            if time.time() + wait_time > deadline:
                return False
            time.sleep(min(wait_time, 0.2))

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now


class RateLimiter:
    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._init_buckets()

    def _init_buckets(self):
        for provider, config in PROVIDER_LIMITS.items():
            requests_per_sec = config.requests_per_minute / 60.0
            self._buckets[provider] = TokenBucket(
                rate=requests_per_sec,
                capacity=config.requests_per_minute,
            )

    def get_bucket(self, provider: str) -> TokenBucket:
        return self._buckets.get(provider, self._buckets["ollama"])

    async def acquire(self, provider: str, timeout: float = 60.0) -> bool:
        bucket = self.get_bucket(provider)
        return await bucket.acquire(count=1, timeout=timeout)

    def sync_acquire(self, provider: str, timeout: float = 60.0) -> bool:
        bucket = self.get_bucket(provider)
        return bucket.sync_acquire(count=1, timeout=timeout)

    def wrap_provider_name(self, model: str) -> str:
        model_lower = model.lower()
        if "gemini" in model_lower:
            return "gemini"
        if "claude" in model_lower or "anthropic" in model_lower:
            return "anthropic"
        if "gpt" in model_lower or "openai" in model_lower or "o1" in model_lower or "o3" in model_lower:
            return "openai"
        if "groq" in model_lower or "llama" in model_lower:
            return "groq"
        if "qwen" in model_lower or "ollama" in model_lower:
            return "ollama"
        if "timps" in model_lower:
            return "timps-coder"
        if "mcp" in model_lower:
            return "mcp_sampler"
        return "ollama"


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
