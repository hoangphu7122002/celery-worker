import uuid

import redis

from config import settings

_RUN_ID_KEY = "zendesk:llm_limit:run_id"


def _run_id() -> str | None:
    try:
        r = redis.from_url(settings.redis.url)
        run_id = r.get(_RUN_ID_KEY)
        return run_id.decode() if isinstance(run_id, (bytes, bytearray)) else run_id
    except Exception:
        return None


def init_zendesk_llm_limit(*, reset: bool) -> None:
    """Set run_id in Redis. Routes call this before enqueueing."""
    if not settings.zendesk_llm_limit_enabled:
        return
    try:
        r = redis.from_url(settings.redis.url)
        if reset:
            r.delete(_RUN_ID_KEY)
        run_id_value = str(uuid.uuid4())
        ttl = settings.zendesk_llm_limit_ttl_seconds
        if r.set(_RUN_ID_KEY, run_id_value, ex=ttl, nx=not reset) is None:
            return
        count_key = f"zendesk:llm_limit:{run_id_value}:count"
        r.set(count_key, 0, ex=ttl, nx=False)
    except Exception:
        pass


def should_run_llm_for_ticket(ticket_id: int) -> bool:
    """Return True if this ticket should call the LLM (atomic: not seen + count within limit)."""
    if not settings.zendesk_llm_limit_enabled:
        return True
    active_run_id = _run_id()
    if not active_run_id:
        return False
    ticket_key = f"zendesk:llm_limit:{active_run_id}:ticket:{ticket_id}"
    count_key = f"zendesk:llm_limit:{active_run_id}:count"
    lua = """
    local ticket_key, count_key = KEYS[1], KEYS[2]
    local limit, ttl = tonumber(ARGV[1]), tonumber(ARGV[2])
    if redis.call('EXISTS', ticket_key) == 1 then return 0 end
    local new_count = redis.call('INCR', count_key)
    redis.call('EXPIRE', count_key, ttl)
    if new_count > limit then return 0 end
    redis.call('SET', ticket_key, '1', 'EX', ttl)
    return 1
    """
    try:
        r = redis.from_url(settings.redis.url)
        limit = settings.zendesk_llm_limit_tickets_per_run
        ttl = settings.zendesk_llm_limit_ttl_seconds
        allowed = r.eval(lua, 2, ticket_key, count_key, limit, ttl)
        return int(allowed) == 1
    except Exception:
        return True
