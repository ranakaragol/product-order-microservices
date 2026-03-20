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

## Dispatcher Security Gate (Adım 1)
- Dispatcher token doğrulamasına ek olarak servis + HTTP method bazlı yetki kontrolü uygular.
- Kullanıcı erişim profilleri dispatcher'ın izole verisinde (`dispatcher_db.access_profiles`) tutulur.
- `roles` ve `service_permissions` alanları birleştirilerek karar verilir.

Örnek `access_profiles` dokümanı:
```json
{
	"username": "ops_user",
	"roles": ["order_reader"],
	"service_permissions": {
		"products": ["GET"],
		"orders": ["GET"]
	}
}
```

Varsayılan davranış:
- Yetki, sadece dispatcher DB'deki profile kayıtlarından veya `DISPATCHER_ACCESS_PROFILES_JSON` ile açıkça verilen bootstrap profillerden gelir.
- Sadece username eşleşmesiyle (ör. `admin`) otomatik ayrıcalık verilmez.

## Network Isolation Kanıtı
Sistemde dış dünyaya açık tek port `dispatcher` servisidir. Diğer servislerde `ports` tanımı yoktur ve hepsi `internal_network` içindedir.

Doğrulama komutları:
```bash
docker compose -f src/docker-compose.yml config
docker compose -f src/docker-compose.yml ps
docker inspect product_service --format '{{json .NetworkSettings.Ports}}'
docker inspect order_service --format '{{json .NetworkSettings.Ports}}'
docker inspect auth_service --format '{{json .NetworkSettings.Ports}}'
docker inspect dispatcher --format '{{json .NetworkSettings.Ports}}'
```

Beklenen sonuç:
- `auth_service`, `product_service`, `order_service` için port map boş (`null`/`{}`).
- `dispatcher` için `8000/tcp` hosta maplenmiş olmalı.