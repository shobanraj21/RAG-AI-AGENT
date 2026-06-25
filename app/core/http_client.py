import httpx

TIMEOUT = httpx.Timeout(connect=5, read=20, write=20, pool=5)
LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)

async_client = httpx.AsyncClient(
    timeout=TIMEOUT,
    limits=LIMITS
)