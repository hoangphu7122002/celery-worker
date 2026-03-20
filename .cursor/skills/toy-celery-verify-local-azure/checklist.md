# Verification Checklist

Copy-paste checkboxes for local and Azure.

## Local

- [ ] Redis running: `redis-cli -u redis://localhost:6379/0 PING` → PONG
- [ ] Worker starts: `celery -A worker worker -l info` → "connected"
- [ ] Inspect: `celery -A worker inspect ping` (worker running)
- [ ] HTTP enqueue: `curl -X POST .../jobs/add?x=1&y=2` → worker log shows task
- [ ] Route test: patch `.delay`, assert call
- [ ] Task test: `task.run(1, 2)` returns 3

## Azure

- [ ] API and worker share same REDIS_URL (rediss)
- [ ] Worker has SSL config when scheme is rediss
- [ ] Worker scale > 0
- [ ] Enqueue from deployed API → worker log shows task
- [ ] Log Analytics: query for task received / errors
