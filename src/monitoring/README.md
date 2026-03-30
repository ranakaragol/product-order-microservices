# Monitoring Stack

Bu monitoring kurulumu bilinçli olarak küçük tutuldu ve demo odaklı hazırlandı.

## Start Commands

Komutları `src/` dizininden çalıştırın.

Default runtime:

```bash
docker compose up -d --build
```

Monitoring profile:

```bash
docker compose --profile monitoring up -d prometheus grafana
```

Stop everything:

```bash
docker compose --profile monitoring down
```

## Endpoints

- Dispatcher: `http://localhost:8000`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Grafana login: `admin` / `admin`
- Provisioned dashboard: `Dispatcher Overview`

## Dashboard Panels

- `Requests (15m)`: son 15 dakikadaki toplam dispatcher istek sayısı
- `Status Codes (15m)`: son 15 dakikadaki durum kodu bazlı istek dağılımı
- `Request Latency P95`: dispatcher istek gecikmesinin `%95` persentil değeri

## Validation Steps

1. Varsayılan runtime'ı başlatın.
2. Monitoring profilini başlatın.
3. Dispatcher'a örnek trafik üretin:

```bash
curl http://localhost:8000/
curl http://localhost:8000/products
curl http://localhost:8000/unknown
```

4. En az bir Prometheus scrape aralığı kadar bekleyin.
5. Prometheus target durumunu kontrol edin:

```bash
curl http://localhost:9090/api/v1/targets
```

6. Toplam istek ve durum kodu dağılımını kontrol edin:

```bash
curl -G http://localhost:9090/api/v1/query --data-urlencode 'query=sum(dispatcher_http_requests_total)'
curl -G http://localhost:9090/api/v1/query --data-urlencode 'query=sum by (status_code) (dispatcher_http_requests_total)'
curl -G http://localhost:9090/api/v1/query --data-urlencode 'query=histogram_quantile(0.95, sum by (le) (rate(dispatcher_http_request_duration_seconds_bucket[5m])))'
```

7. Grafana provisioning sonucunu doğrulayın:

```bash
curl -u admin:admin 'http://localhost:3000/api/search?query=Dispatcher%20Overview'
```

## Validation Highlights

30 Mart 2026 tarihinde doğrulandı:

- `dispatcher:8000` için Prometheus target health değeri `up` oldu
- `sum(dispatcher_http_requests_total)` iki trafik turundan sonra `6` döndürdü
- `sum by (status_code) (dispatcher_http_requests_total)` sorgusu `200=2`, `401=2`, `404=2` döndürdü
- `histogram_quantile(0.95, ...)` sorgusu ikinci scrape penceresinden sonra yaklaşık `0.0097` saniye döndürdü
- Grafana API araması provision edilmiş `dispatcher-overview` dashboard'unu döndürdü

## Notes

- Dispatcher metrikleri Mongo `traffic_logs` yapısının yerine geçmez; ayrıntılı istek logları dispatcher Mongo içinde tutulmaya devam eder.
- `/metrics` endpoint'i kendi oluşturduğu gürültüyü önlemek için hem Prometheus sayaçlarından hem Mongo traffic log kayıtlarından hariç tutulur.
- Latency paneli, Prometheus en az iki değişen örnek scrape edene kadar ilk açılışta kısa süre `NaN` gösterebilir.

## Residual Risk

- Bu stack bilinçli olarak minimal tutuldu; alerting, kalıcı veri ayarı ve Grafana demo kimlik bilgileri için ek güvenlik sıkılaştırması içermiyor.

## Next Small Step

- Ders demosunda daha güçlü bir anlatım gerekirse route seviyesinde ek bir dashboard satırı veya basit bir alert kuralı eklenebilir.
