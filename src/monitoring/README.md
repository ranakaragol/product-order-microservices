# Monitoring and Grafana Workflow

This document explains how to run and validate the monitoring stack for this repository.

## Prerequisites

- Docker Desktop (or Docker Engine) running
- Docker Compose v2
- Run all commands from the repository root:
  - `C:\Users\husoelrey\Documents\Projects\product-order-microservices`

## 1. Start Runtime Stack

```bash
docker compose -f src/docker-compose.yml up -d --build
```

## 2. Start Monitoring Profile

```bash
docker compose -f src/docker-compose.yml --profile monitoring up -d prometheus grafana
```

## 3. Monitoring Endpoints

- Dispatcher: http://localhost:8000
- Dispatcher metrics endpoint: http://localhost:8000/metrics
- Prometheus UI/API: http://localhost:9090
- Grafana UI/API: http://localhost:3000

## 4. Grafana Login

- Username: `admin` (default)
- Password: `admin` (default)
- These can be overridden via compose environment values:
  - `GRAFANA_ADMIN_USER`
  - `GRAFANA_ADMIN_PASSWORD`

## 5. Provisioned Dashboard

- Dashboard title: `Dispatcher Overview`
- Dashboard UID: `dispatcher-overview`
- Provisioning folder: `Dispatcher`

## 6. Sample Traffic Generation Commands

Simple traffic (quick check):

```bash
curl -i http://localhost:8000/
curl -i http://localhost:8000/products
curl -i http://localhost:8000/unknown
```

Authenticated sample traffic (PowerShell):

```powershell
$user = @{ username = "monitoring_user"; password = "monitoring_pass" } | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:8000/auth/register" -Method POST -ContentType "application/json" -Body $user -UseBasicParsing
$login = Invoke-RestMethod -Uri "http://localhost:8000/auth/login" -Method POST -ContentType "application/json" -Body $user
$headers = @{ Authorization = "Bearer $($login.token)" }
Invoke-WebRequest -Uri "http://localhost:8000/products" -Method GET -Headers $headers -UseBasicParsing
Invoke-WebRequest -Uri "http://localhost:8000/products" -Method POST -Headers $headers -ContentType "application/json" -Body '{"name":"Sample","description":"demo","price":9.99,"stock":3}' -UseBasicParsing
```

## 7. Prometheus Validation Queries

Target health:

```bash
curl -s http://localhost:9090/api/v1/targets
```

Raw counter totals:

```bash
curl -s -G http://localhost:9090/api/v1/query --data-urlencode 'query=sum(dispatcher_http_requests_total)'
curl -s -G http://localhost:9090/api/v1/query --data-urlencode 'query=sum by (status_code) (dispatcher_http_requests_total)'
```

Dashboard panel-equivalent queries:

```bash
curl -s -G http://localhost:9090/api/v1/query --data-urlencode 'query=sum(increase(dispatcher_http_requests_total[15m]))'
curl -s -G http://localhost:9090/api/v1/query --data-urlencode 'query=sum by (status_code) (increase(dispatcher_http_requests_total[15m]))'
curl -s -G http://localhost:9090/api/v1/query --data-urlencode 'query=histogram_quantile(0.95, sum by (le) (rate(dispatcher_http_request_duration_seconds_bucket[5m])))'
```

## 8. Verify Grafana Provisioning

Datasource check:

```bash
curl -s -u admin:admin http://localhost:3000/api/datasources/name/Prometheus
```

Dashboard search check:

```bash
curl -s -u admin:admin 'http://localhost:3000/api/search?query=Dispatcher%20Overview'
```

Expected:
- Datasource `Prometheus` exists with `uid=prometheus`.
- Dashboard search returns `dispatcher-overview` in folder `Dispatcher`.

## 9. What the Dashboard Shows

- `Requests (15m)`: Total dispatcher request volume in the last 15 minutes.
- `Status Codes (15m)`: 15-minute request distribution by HTTP status code.
- `Request Latency P95`: 95th percentile dispatcher request latency.

If latency shows `NaN` right after startup, wait for additional Prometheus scrapes and refresh.

## 10. Real Validation Notes (Observed on 2026-04-02)

Validation was run locally in this environment with real Docker containers.

Observed highlights:
- `docker compose -f src/docker-compose.yml up -d --build` completed and all runtime services started.
- `docker compose -f src/docker-compose.yml --profile monitoring up -d prometheus grafana` started monitoring services.
- Prometheus target for `dispatcher:8000` reported `health: up`.
- Sample traffic produced: `200`, `401`, `404`, `403` responses (and one earlier `422` during malformed request testing).
- `sum(dispatcher_http_requests_total)` returned `7` at capture time.
- `sum by (status_code) (dispatcher_http_requests_total)` returned:
  - `200 = 3`
  - `401 = 2`
  - `404 = 1`
  - `422 = 1`
- `histogram_quantile(0.95, ...)` returned approximately `0.4198` seconds.
- Grafana API search returned dashboard `uid=dispatcher-overview`.
- Grafana datasource API returned `name=Prometheus`, `uid=prometheus`, `readOnly=true`.

## 11. Stop Commands

Stop monitoring services:

```bash
docker compose -f src/docker-compose.yml --profile monitoring stop prometheus grafana
```

Stop all services:

```bash
docker compose -f src/docker-compose.yml down
```