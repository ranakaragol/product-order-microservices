# Product-Order Microservices

## Amaç
Python + FastAPI kullanarak Ürün / Sipariş mikroservis sistemi geliştirmek.

## Teknoloji Yığını
- Python + FastAPI
- MongoDB (her servis için ayrı)
- Docker + Docker Compose
- pytest (TDD)
- Locust (yük testi)
- Grafana (log & trafik)

## Dispatcher Yetkilendirme Profilleri
Dispatcher, `/products` ve `/orders` isteklerinde yetkilendirmeyi merkezi olarak uygular. Token yoksa veya geçersizse `401` döner; token geçerli olsa bile token içindeki `sub` değeri için rota ve yöntem izni yoksa `403` döner. Açık bir profil tanımlı olmayan doğrulanmış kullanıcılar ise varsayılan olarak `default-authenticated` okuma profiline düşer.

| Örnek durum | Örnek istek | Beklenen davranış |
| --- | --- | --- |
| Eksik veya geçersiz token | `GET /products` | Dispatcher isteği aşağı servise iletmeden `401` döner. |
| `default-authenticated` | `GET /products` ve `POST /products` | Okuma isteği başarılı akışta `200`, yazma isteği `403` döner. |
| `bob` | `GET /orders` ve `POST /orders` | Okuma isteği başarılı akışta `200`, yazma isteği `403` döner. |
| `alice` | `POST /products` | Yükseltilmiş erişim nedeniyle istek geçirilir; başarılı oluşturma akışında tipik sonuç `201` olur. |

## Baseline Test Workflow (P0)
Run tests per service from each service directory:

```bash
cd src/auth_service && pytest tests
cd src/dispatcher && pytest tests
cd src/product_service && pytest tests
cd src/order_service && pytest tests
```

## Docker Runtime Workflow

Start the full system (runtime profile):

```bash
docker compose -f src/docker-compose.yml up --build
```

## Monitoring Workflow

This section explains how to run and validate the monitoring stack.

### Prerequisites

- Docker Desktop (or Docker Engine) running
- Docker Compose v2
- Run all commands from the repository root:
	- `C:\Users\husoelrey\Documents\Projects\product-order-microservices`

### 1. Start Runtime Stack

```bash
docker compose -f src/docker-compose.yml up -d --build
```

### 2. Start Monitoring Profile

```bash
docker compose -f src/docker-compose.yml --profile monitoring up -d prometheus grafana
```

### 3. Monitoring Endpoints

- Dispatcher: http://localhost:8000
- Dispatcher metrics endpoint: http://localhost:8000/metrics
- Prometheus UI/API: http://localhost:9090
- Grafana UI/API: http://localhost:3000

### 4. Grafana Login

- Username: `admin` (default)
- Password: `admin` (default)
- These can be overridden via compose environment values:
	- `GRAFANA_ADMIN_USER`
	- `GRAFANA_ADMIN_PASSWORD`

### 5. Provisioned Dashboard

- Dashboard title: `Dispatcher Overview`
- Dashboard UID: `dispatcher-overview`
- Provisioning folder: `Dispatcher`

### 6. Sample Traffic Generation Commands

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

### 7. Prometheus Validation Queries

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

### 8. Verify Grafana Provisioning

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

### 9. What the Dashboard Shows

- `Requests (15m)`: Total dispatcher request volume in the last 15 minutes.
- `Status Codes (15m)`: 15-minute request distribution by HTTP status code.
- `Request Latency P95`: 95th percentile dispatcher request latency.

If latency shows `NaN` right after startup, wait for additional Prometheus scrapes and refresh.

### 10. Real Validation Notes (Observed on 2026-04-02)

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

### 11. Stop Commands

Stop monitoring services:

```bash
docker compose -f src/docker-compose.yml --profile monitoring stop prometheus grafana
```

Stop all services:

```bash
docker compose -f src/docker-compose.yml down
```

## Docker Test Workflow (Separated from Runtime)

The compose file provides dedicated `test` profile services with dev dependencies installed.
These test containers are separate from the default runtime stack and use a consistent `/workspace` bind mount plus `pytest tests` command pattern.

Use these commands to run tests without installing packages inside running runtime containers:

```bash
docker compose -f src/docker-compose.yml --profile test run --rm auth_tests
docker compose -f src/docker-compose.yml --profile test run --rm dispatcher_tests
docker compose -f src/docker-compose.yml --profile test run --rm product_tests
docker compose -f src/docker-compose.yml --profile test run --rm order_tests
```

Run all test-profile services in one line:

```bash
docker compose -f src/docker-compose.yml --profile test run --rm auth_tests && docker compose -f src/docker-compose.yml --profile test run --rm dispatcher_tests && docker compose -f src/docker-compose.yml --profile test run --rm product_tests && docker compose -f src/docker-compose.yml --profile test run --rm order_tests
```

If Docker state becomes inconsistent, clean and rebuild safely:

```bash
docker compose -f src/docker-compose.yml down --remove-orphans
docker compose -f src/docker-compose.yml up --build
```

For compose validation and network isolation checks:

```bash
docker compose -f src/docker-compose.yml config
docker compose -f src/docker-compose.yml --profile test config
```

Expected baseline:
- only dispatcher publishes a host port,
- auth/product/order remain internal-only,
- runtime and test workflows stay separated,
- local `pytest` runs still work from each service directory.
