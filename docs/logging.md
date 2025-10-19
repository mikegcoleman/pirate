# Unified Logging for Mr. Bones Pirate Assistant

This document describes the unified JSON logging infrastructure for centralized collection in Grafana Loki via Promtail.

## Overview

Both the Python client (Raspberry Pi) and Node.js API (Windows) now output structured JSON logs with matching schemas and correlated request IDs (reqId) for end-to-end request tracing.

## JSON Log Schema

All log entries follow this consistent schema:

```json
{
  "ts": "2025-10-19T18:01:23.456Z",
  "level": "info",
  "reqId": "27077ed3",
  "msg": "TTS generation completed",
  "meta": {
    "chunk": "2/3",
    "duration_ms": 404
  }
}
```

### Fields

- **ts** (string, required): Timestamp in UTC ISO-8601 format with milliseconds and `Z` suffix
- **level** (string, required): Log level - one of: `debug`, `info`, `warn`, `error`
- **reqId** (string, nullable): 8-character lowercase hex request ID for correlation (null for non-request logs)
- **msg** (string, required): Human-readable log message
- **meta** (object, optional): Additional structured metadata (omitted if empty)

### Stack Traces

When `LOG_STACK=1` and an error occurs, the `meta.stack` field contains the full stack trace as a string.

## Environment Variables

### Python Client (`stt/.env`)

```bash
# Logging Configuration
LOG_LEVEL=info              # debug, info, warn, error (default: info)
LOG_FILE=/var/log/mr-bones/client.log  # Log file path (with rotation)
LOG_STACK=0                 # Include stack traces in error logs (0 or 1)
REQUEST_ID_HEADER=X-Request-Id  # HTTP header name for request ID
```

### Node.js API (`llm-api/.env`)

```bash
# Logging Configuration
LOG_LEVEL=info              # debug, info, warn, error (default: info)
LOG_STACK=0                 # Include stack traces in error logs (0 or 1)
REQUEST_ID_HEADER=X-Request-Id  # HTTP header name for request ID

# Note: Node.js logs to stdout only - redirect to file externally
```

## Request ID (reqId) Correlation

### How It Works

1. **Python Client (Conversation Turn)**:
   - Generates a new 8-char hex reqId at the start of each conversation turn
   - Sets it in context using `contextvars` for thread-safe propagation
   - Includes it in all HTTP requests via `X-Request-Id` header
   - Logs every action in that turn with the same reqId

2. **Node.js API (HTTP Request)**:
   - Middleware checks for incoming `X-Request-Id` header (case-insensitive)
   - Generates a new reqId if header is missing
   - Attaches reqId to `req.reqId` for use throughout the request
   - Echoes reqId in response via `X-Request-Id` header
   - Logs every action in that request with the same reqId

3. **End-to-End Tracing**:
   - Same reqId flows through: client → API → LLM → TTS → response → client
   - Query Loki for a specific reqId to see the entire request lifecycle

### Request ID Format

- **Length**: 8 characters
- **Character Set**: Lowercase hexadecimal (`[0-9a-f]`)
- **Generation**: First 8 characters of UUID v4 hex representation
- **Example**: `27077ed3`

### Background Operations

- **Request-Tied Background Work**: Inherits reqId from parent context (e.g., filler player during API call)
- **True Background Work**: No reqId, but includes `opId` (operation ID, same 8-char format) in meta for tracing

## Log Rotation

### Python Client (Raspberry Pi)

Automatic rotation using `RotatingFileHandler`:
- **Max Size**: 5 MB per file
- **Backup Count**: 5 files
- **Total Disk Usage**: ~25 MB maximum
- **Rotation Behavior**: When `client.log` reaches 5MB, it's renamed to `client.log.1`, `client.log.2`, etc.

### Node.js API (Windows)

Logs are written to stdout only. Use external log rotation:

#### Option A: Redirect + Task Scheduler (Recommended)

1. **Redirect stdout to file when running the service**:
   ```powershell
   node server.js >> C:\logs\mr-bones\api.log 2>&1
   ```

2. **Create PowerShell rotation script** (`C:\scripts\rotate-mr-bones-logs.ps1`):
   ```powershell
   # Rotate Mr. Bones API logs
   $logFile = "C:\logs\mr-bones\api.log"
   $maxSizeMB = 5
   $maxBackups = 5

   if (Test-Path $logFile) {
       $size = (Get-Item $logFile).Length / 1MB
       if ($size -ge $maxSizeMB) {
           # Rotate existing backups
           for ($i = $maxBackups - 1; $i -ge 1; $i--) {
               $old = "$logFile.$i"
               $new = "$logFile.$($i + 1)"
               if (Test-Path $old) {
                   if ($i -eq ($maxBackups - 1)) {
                       Remove-Item $old -Force
                   } else {
                       Move-Item $old $new -Force
                   }
               }
           }
           # Rotate current log
           Move-Item $logFile "$logFile.1" -Force
           New-Item $logFile -ItemType File
       }
   }
   ```

3. **Schedule via Task Scheduler**:
   - Trigger: Daily at 3:00 AM
   - Action: `powershell.exe -File C:\scripts\rotate-mr-bones-logs.ps1`
   - Run whether user is logged on or not

#### Option B: Third-Party Tool

Use a Windows log rotation tool like `logrotate-win` or `nxlog`.

## Promtail Configuration

### Python Client (Raspberry Pi)

Save as `/etc/promtail/config-mr-bones-client.yml`:

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /var/lib/promtail/positions-mr-bones-client.yaml

clients:
  - url: http://<LOKI_SERVER>:3100/loki/api/v1/push

scrape_configs:
  - job_name: mr-bones-client
    static_configs:
      - targets:
          - localhost
        labels:
          app: mr-bones
          component: client
          host: raspberry-pi
          __path__: /var/log/mr-bones/client.log

    # JSON parsing
    pipeline_stages:
      - json:
          expressions:
            ts: ts
            level: level
            reqId: reqId
            msg: msg
            meta: meta

      - timestamp:
          source: ts
          format: RFC3339Nano

      - labels:
          level:
          reqId:

      - output:
          source: msg
```

### Node.js API (Windows)

Save as `C:\promtail\config-mr-bones-api.yml`:

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: C:\promtail\positions-mr-bones-api.yaml

clients:
  - url: http://<LOKI_SERVER>:3100/loki/api/v1/push

scrape_configs:
  - job_name: mr-bones-api
    static_configs:
      - targets:
          - localhost
        labels:
          app: mr-bones
          component: api
          host: windows-server
          __path__: C:\logs\mr-bones\api.log

    # JSON parsing
    pipeline_stages:
      - json:
          expressions:
            ts: ts
            level: level
            reqId: reqId
            msg: msg
            meta: meta

      - timestamp:
          source: ts
          format: RFC3339Nano

      - labels:
          level:
          reqId:

      - output:
          source: msg
```

### Running Promtail

**Raspberry Pi (Linux)**:
```bash
sudo systemctl enable promtail
sudo systemctl start promtail
```

**Windows**:
```powershell
# Run as Windows Service or in PowerShell
promtail.exe -config.file=C:\promtail\config-mr-bones-api.yml
```

## LogQL Query Examples

### Trace a Specific Request

```logql
{app="mr-bones"} |= "27077ed3"
```

### All Errors in Last Hour

```logql
{app="mr-bones", level="error"} | json
```

### Client Errors Only

```logql
{app="mr-bones", component="client", level="error"}
```

### API Response Times

```logql
{app="mr-bones", component="api"}
| json
| msg="TTS generation completed"
| unwrap duration_ms
| quantile_over_time(0.95, [1h])
```

### Request Latency by Component

```logql
sum by (component) (
  rate({app="mr-bones"} | json | unwrap duration_ms [5m])
)
```

### Requests Per Minute

```logql
sum(rate({app="mr-bones", component="client"}
| json
| msg="User speech transcribed" [1m])) * 60
```

### Filter by Request ID and Show Full Timeline

```logql
{app="mr-bones"}
| json
| reqId="27077ed3"
| line_format "{{.ts}} [{{.level}}] {{.msg}} {{.meta}}"
```

### Count Errors by Message

```logql
sum by (msg) (
  count_over_time({app="mr-bones", level="error"} [24h])
)
```

## Testing Logging

### Python Client

```bash
cd stt
python -c "
from logger_utils import get_logger, generate_request_id, set_request_id

logger = get_logger('test')
req_id = generate_request_id()
set_request_id(req_id)

logger.info('Test message', duration_ms=123, user='test')
logger.error('Test error', exc_info=True, error_code='TEST123')
"
```

Expected output (single JSON line):
```json
{"ts":"2025-10-19T18:01:23.456Z","level":"info","reqId":"27077ed3","msg":"Test message","meta":{"duration_ms":123,"user":"test"}}
```

### Node.js API

```bash
cd llm-api
curl -X POST http://localhost:8080/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: test1234" \
  -d '{
    "model": "llama3.2:latest",
    "messages": [{"role": "user", "content": "Hi"}]
  }'
```

Check logs for `reqId: "test1234"` in all log entries for this request.

## Common Issues

### Logs Not Appearing in Loki

1. **Check Promtail is running**:
   ```bash
   # Linux
   systemctl status promtail

   # Windows
   Get-Process promtail
   ```

2. **Verify log file permissions**:
   ```bash
   # Promtail needs read access
   sudo chmod 644 /var/log/mr-bones/client.log
   ```

3. **Check Promtail can reach Loki**:
   ```bash
   curl http://<LOKI_SERVER>:3100/ready
   ```

### Request IDs Not Correlating

1. **Verify header name matches** in both client and API `.env` files
2. **Check CORS allows the header** (API only)
3. **Ensure middleware runs before routes** (API only)

### Python Log Rotation Not Working

1. **Check directory permissions**:
   ```bash
   sudo mkdir -p /var/log/mr-bones
   sudo chown pi:pi /var/log/mr-bones
   ```

2. **Verify LOG_FILE environment variable**:
   ```bash
   echo $LOG_FILE
   ```

## Best Practices

1. **Use Appropriate Log Levels**:
   - `debug`: Detailed diagnostic info (usually disabled in production)
   - `info`: Normal operational messages
   - `warn`: Warning messages (degraded functionality, but still working)
   - `error`: Error messages (request failed, but service continues)

2. **Include Relevant Metadata**:
   - Always include timing info (duration_ms) for operations
   - Include resource identifiers (chunk_id, file, etc.)
   - Add error context (status_code, error_message)

3. **Request ID Hygiene**:
   - Generate reqId as early as possible in request flow
   - Never modify reqId during a request
   - Always propagate reqId to downstream services

4. **Avoid Sensitive Data**:
   - Never log passwords, API keys, or tokens
   - Truncate long user inputs (first 50-100 chars)
   - Consider PII implications before logging user data

## Future Enhancements

- [ ] Add trace ID for multi-request conversations
- [ ] Implement log sampling for high-volume debug logs
- [ ] Add structured error codes for easier filtering
- [ ] Create Grafana dashboards for common queries
- [ ] Set up Loki alerts for error rate thresholds
