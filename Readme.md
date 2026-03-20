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

For compose validation and network isolation checks:

```bash
docker compose -f src/docker-compose.yml config
```

Expected baseline:
- only dispatcher publishes a host port,
- auth/product/order remain internal-only,
- auth unit tests do not require a locally running Mongo instance.