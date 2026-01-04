# Observability & DevOps Hygiene

This document defines observability standards for the autonomous software factory.

## Philosophy

**You can't fix what you can't see.** Every production system needs:
1. **Health checks** - Is it up? Is it healthy?
2. **Metrics** - How is it performing? What's the trend?
3. **Logs** - What happened? Why did it fail?
4. **Alerts** - Proactive notification before users notice

## Health Endpoint Standards

### Basic Health (`/health`)
Returns 200 if the service can handle requests.

```python
@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}
```

### Deep Health (`/health/ready`)
Verifies all dependencies are accessible. Returns 503 if degraded.

```python
@app.get("/health/ready")
async def health_ready(db: Session = Depends(get_db)) -> dict:
    checks = {}

    # Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Add other dependency checks (Redis, external APIs, etc.)

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
        status_code=status_code
    )
```

### Liveness vs Readiness
- **Liveness** (`/health`): "Is the process alive?" - Used by container orchestrators to restart
- **Readiness** (`/health/ready`): "Can it handle traffic?" - Used for load balancer routing

## Application Metrics

### Essential Metrics (The Four Golden Signals)

1. **Latency** - Request duration (p50, p95, p99)
2. **Traffic** - Requests per second
3. **Errors** - Error rate (4xx, 5xx)
4. **Saturation** - Resource utilization (CPU, memory, connections)

### Business KPIs

Track metrics that matter to the product:
- Active users (DAU/WAU/MAU)
- Feature usage (conversations created, messages sent)
- Conversion rates (if applicable)
- Error rates by feature

### Implementation Options

**Option 1: OpenTelemetry (Recommended)**
```python
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider

meter = metrics.get_meter("myapp")
request_counter = meter.create_counter("http_requests_total")
latency_histogram = meter.create_histogram("http_request_duration_seconds")
```

**Option 2: Prometheus Client**
```python
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')
```

**Option 3: Railway Built-in**
Railway provides CPU, memory, and network metrics out of the box. For custom metrics, use their OpenTelemetry integration.

## Structured Logging Standards

### Required Fields
Every log entry should include:
- `timestamp` - ISO 8601 format
- `level` - DEBUG, INFO, WARNING, ERROR, CRITICAL
- `service` - Service name
- `request_id` - Correlation ID for request tracing
- `message` - Human-readable description

### Example
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "user_registered",
    user_id=user.id,
    username=user.username,
    registration_method="email"
)
```

### What to Log
- **INFO**: Normal operations (user actions, API calls)
- **WARNING**: Recoverable issues (retries, fallbacks)
- **ERROR**: Failures that need attention (exceptions, timeouts)
- **DEBUG**: Detailed debugging info (only in dev)

### What NOT to Log
- Passwords, tokens, API keys
- Full credit card numbers
- Personal health information
- Anything that could identify users in violation of privacy laws

## Alerting Strategy

### Alert Levels

| Level | Response Time | Examples |
|-------|--------------|----------|
| P1/SEV1 | Immediate | Production down, data loss |
| P2/SEV2 | 15 minutes | Major feature broken, high error rate |
| P3/SEV3 | Next business day | Performance degradation, minor bugs |

### What to Alert On

**Immediate (P1):**
- Health check failures (>2 consecutive)
- Error rate >10% for 5 minutes
- Database unreachable

**Soon (P2):**
- Error rate >5% for 10 minutes
- P95 latency >2s for 10 minutes
- Disk/memory >90%

**Eventually (P3):**
- Error rate >1% for 1 hour
- Slow queries (>1s) increasing
- Certificate expiring in <14 days

### Alert Fatigue Prevention
- Only alert on actionable items
- Group related alerts
- Set appropriate thresholds (not too sensitive)
- Include runbook links in alerts

## DevOps Agent Responsibilities

The DevOps agent should:

1. **Monitor** - Check health endpoints every 5 minutes
2. **Detect** - Identify anomalies in metrics/logs
3. **Alert** - Create issues for problems that need attention
4. **Diagnose** - Pull logs, check metrics, identify root cause
5. **Remediate** - Restart services, scale resources (within limits)
6. **Report** - Weekly audit of monitoring effectiveness

## Railway-Specific Setup

### Observability Dashboard
Railway provides built-in dashboards for:
- CPU and memory usage
- Network I/O
- Deployment history
- Log streaming

Access via: Railway Dashboard → Project → Observability

### OpenTelemetry Integration
Railway supports OTel collectors. To set up:

1. Deploy an OTel collector service
2. Configure your app to send traces/metrics to collector
3. Export to your preferred backend (Grafana, Datadog, etc.)

See: https://docs.railway.app/guides/observability

### Log Filtering
Use Railway's log viewer to filter by:
- Service name
- Time range
- Log level
- Custom search terms

## Checklist for New Features

Before shipping any feature, verify:

- [ ] Health endpoint updated if new dependencies added
- [ ] Key operations have INFO-level logging
- [ ] Errors are logged with context (not just stack trace)
- [ ] Metrics added for new endpoints/features
- [ ] Alerts configured for failure scenarios
- [ ] Runbook updated with new failure modes

## Implementation Priority

For a new project:

1. **Week 1**: Basic health endpoint, structured logging
2. **Week 2**: Deep health checks, request logging middleware
3. **Week 3**: Application metrics (latency, errors)
4. **Month 2**: Business KPIs, alerting rules
5. **Ongoing**: Refine thresholds, add metrics as needed
