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

## Docker Test Workflow (Separated from Runtime)

The compose file provides `test` profile services with dev dependencies installed.
Use these commands to run tests without manual `pip install` in running runtime containers:

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
docker compose -f src/docker-compose.yml build --no-cache
docker compose -f src/docker-compose.yml up -d
```

For compose validation and network isolation checks:

```bash
docker compose -f src/docker-compose.yml config
```

Expected baseline:
- only dispatcher publishes a host port,
- auth/product/order remain internal-only,
- auth unit tests do not require a locally running Mongo instance.