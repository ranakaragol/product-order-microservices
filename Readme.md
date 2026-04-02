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

For Prometheus + Grafana startup, endpoint checks, validation queries, and provisioning verification, see:

- `src/monitoring/README.md`

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
