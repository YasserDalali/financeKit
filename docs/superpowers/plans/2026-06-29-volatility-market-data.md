# Volatility MS — Market Data Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the `finrisk-web` frontend, then wire the volatility microservice to open-source market price data (FinancialModelingPrep) via a modular `MarketDataProvider` interface that can be reused elsewhere.

**Architecture:** A `MarketDataProvider` interface lives in `com.finrisk.marketdata`. The FMP implementation lives in `com.finrisk.marketdata.fmp` (self-contained: config, HTTP client, JSON parsing). `MarketDataService` orchestrates "fetch from provider → upsert into `asset_price_history`". A single new endpoint `POST /api/v1/assets/{id}/sync-prices` triggers a sync. Spring wires the provider as a `@Component` — swap the implementation without touching any service code.

**Tech Stack:** Java 21, Spring Boot 3.3, `java.net.http.HttpClient` (built-in, no extra deps), Jackson (already in classpath via Spring Web), JUnit 5 + Mockito (already in test scope). FinancialModelingPrep free-tier API.

## Global Constraints

- No new Maven dependencies for the HTTP client (`java.net.http.HttpClient` ships with JDK 11+)
- `MarketDataProvider` interface must live in `com.finrisk.marketdata` — not inside `fmp` — so other implementations can be dropped in later
- FMP API key is read from `fmp.api-key` Spring property (set via env var `FMP_API_KEY`) — empty key → provider returns empty list gracefully (no exception)
- `finrisk-web` directory and its `docker-compose` service are fully removed
- No new DB migration needed — `upsertForDate` uses a MERGE statement on the existing `asset_price_history` table

---

## File Map

**Delete:**
- `finrisk-web/` (entire directory)

**Modify:**
- `docker-compose.yml` — remove `finrisk-web` service block
- `pom.xml` — remove `finrisk-web` from sonar.sources
- `src/main/java/com/finrisk/dao/AssetPriceHistoryDao.java` — add `upsertForDate`
- `src/main/java/com/finrisk/dao/impl/AssetPriceHistoryDaoJdbc.java` — implement `upsertForDate`
- `src/main/java/com/finrisk/controller/AssetController.java` — add `POST /{id}/sync-prices`
- `src/main/resources/application.yml` — add `fmp.api-key` + `fmp.base-url`

**Create:**
- `src/main/java/com/finrisk/marketdata/MarketDataProvider.java`
- `src/main/java/com/finrisk/marketdata/PricePoint.java`
- `src/main/java/com/finrisk/marketdata/fmp/FmpConfig.java`
- `src/main/java/com/finrisk/marketdata/fmp/FmpMarketDataProvider.java`
- `src/main/java/com/finrisk/service/MarketDataService.java`
- `src/test/java/com/finrisk/service/MarketDataServiceTest.java`
- `src/test/java/com/finrisk/marketdata/fmp/FmpMarketDataProviderTest.java`

---

### Task 1: Delete finrisk-web and clean docker-compose + pom.xml

**Files:**
- Delete: `finrisk-web/`
- Modify: `docker-compose.yml`
- Modify: `pom.xml`

- [ ] **Step 1: Delete the frontend directory**

```bash
cd volatility-ms
rm -rf finrisk-web
```

- [ ] **Step 2: Remove `finrisk-web` service from `docker-compose.yml`**

Open `docker-compose.yml`. Remove the entire `finrisk-web` service block (lines currently reading):

```yaml
  finrisk-web:
    build:
      context: .
      dockerfile: finrisk-web/Dockerfile
    container_name: finrisk-web
    depends_on:
      finrisk-api:
        condition: service_started
    ports:
      - "8081:80"
```

After removal the services are: `sqlserver`, `finrisk-api`, `sonarqube`.

- [ ] **Step 3: Fix `sonar.sources` in `pom.xml`**

In `pom.xml`, find the `<sonar.sources>` property:
```xml
<sonar.sources>src/main/java,finrisk-web/src</sonar.sources>
```
Change it to:
```xml
<sonar.sources>src/main/java</sonar.sources>
```

Also remove the `<sonar.exclusions>` line that references `finrisk-web`:
```xml
<sonar.exclusions>**/node_modules/**,finrisk-web/src/generated/**,finrisk-web/stitch_finrisk_portfolio_management_api/**</sonar.exclusions>
```
→ delete that line entirely (no frontend sources to exclude).

- [ ] **Step 4: Verify the project still compiles**

```bash
set -a && source .env && set +a
mvn -B compile -q
# Expected: BUILD SUCCESS
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml pom.xml
git rm -r finrisk-web
git commit -m "chore: delete finrisk-web frontend — volatility-ms is a pure microservice"
```

---

### Task 2: MarketDataProvider interface + PricePoint record

**Files:**
- Create: `src/main/java/com/finrisk/marketdata/MarketDataProvider.java`
- Create: `src/main/java/com/finrisk/marketdata/PricePoint.java`

**Interfaces:**
- Produces:
  - `PricePoint(LocalDate date, BigDecimal close)`
  - `MarketDataProvider.fetchDailyPrices(String symbol, int days): List<PricePoint>`

- [ ] **Step 1: Create `PricePoint.java`**

```java
package com.finrisk.marketdata;

import java.math.BigDecimal;
import java.time.LocalDate;

public record PricePoint(LocalDate date, BigDecimal close) {}
```

- [ ] **Step 2: Create `MarketDataProvider.java`**

```java
package com.finrisk.marketdata;

import java.util.List;

public interface MarketDataProvider {

    /**
     * Returns up to {@code days} daily closing prices for {@code symbol},
     * newest first. Returns an empty list if the symbol is unknown, the
     * provider is misconfigured, or a network error occurs.
     */
    List<PricePoint> fetchDailyPrices(String symbol, int days);
}
```

- [ ] **Step 3: Verify compilation**

```bash
mvn -B compile -q
# Expected: BUILD SUCCESS
```

- [ ] **Step 4: Commit**

```bash
git add src/main/java/com/finrisk/marketdata/
git commit -m "feat: add MarketDataProvider interface + PricePoint record"
```

---

### Task 3: FMP implementation (FmpConfig + FmpMarketDataProvider)

**Files:**
- Create: `src/main/java/com/finrisk/marketdata/fmp/FmpConfig.java`
- Create: `src/main/java/com/finrisk/marketdata/fmp/FmpMarketDataProvider.java`
- Modify: `src/main/resources/application.yml`

**Interfaces:**
- Consumes: `MarketDataProvider`, `PricePoint`
- Produces: `FmpMarketDataProvider implements MarketDataProvider` registered as `@Component`

FMP historical endpoint:
```
GET https://financialmodelingprep.com/api/v3/historical-price-full/{SYMBOL}?from={YYYY-MM-DD}&apikey={KEY}
```
Response shape (relevant fields):
```json
{
  "historical": [
    { "date": "2024-06-28", "close": 123.45 },
    ...
  ]
}
```

- [ ] **Step 1: Create `FmpConfig.java`**

```java
package com.finrisk.marketdata.fmp;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class FmpConfig {

    @Value("${fmp.api-key:}")
    public String apiKey;

    @Value("${fmp.base-url:https://financialmodelingprep.com/api/v3}")
    public String baseUrl;
}
```

- [ ] **Step 2: Create `FmpMarketDataProvider.java`**

```java
package com.finrisk.marketdata.fmp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.finrisk.marketdata.MarketDataProvider;
import com.finrisk.marketdata.PricePoint;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

@Component
public class FmpMarketDataProvider implements MarketDataProvider {

    private final FmpConfig config;
    private final HttpClient http;
    private final ObjectMapper mapper;

    public FmpMarketDataProvider(FmpConfig config) {
        this.config = config;
        this.http = HttpClient.newHttpClient();
        this.mapper = new ObjectMapper();
    }

    @Override
    public List<PricePoint> fetchDailyPrices(String symbol, int days) {
        if (config.apiKey == null || config.apiKey.isBlank()) {
            return List.of();
        }
        try {
            String from = LocalDate.now().minusDays(days).toString();
            String url = "%s/historical-price-full/%s?from=%s&apikey=%s"
                    .formatted(config.baseUrl, symbol, from, config.apiKey);
            HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                    .GET()
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() != 200) {
                return List.of();
            }
            JsonNode root = mapper.readTree(resp.body());
            JsonNode historical = root.path("historical");
            List<PricePoint> points = new ArrayList<>();
            for (JsonNode node : historical) {
                LocalDate date = LocalDate.parse(node.get("date").asText());
                BigDecimal close = new BigDecimal(node.get("close").asText());
                points.add(new PricePoint(date, close));
            }
            return points;
        } catch (Exception e) {
            return List.of();
        }
    }
}
```

- [ ] **Step 3: Add FMP properties to `application.yml`**

Append to `src/main/resources/application.yml`:
```yaml
fmp:
  api-key: ${FMP_API_KEY:}
  base-url: https://financialmodelingprep.com/api/v3
```

- [ ] **Step 4: Write unit test for FmpMarketDataProvider**

Create `src/test/java/com/finrisk/marketdata/fmp/FmpMarketDataProviderTest.java`:

```java
package com.finrisk.marketdata.fmp;

import com.finrisk.marketdata.PricePoint;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class FmpMarketDataProviderTest {

    @Test
    void returnsEmptyWhenApiKeyBlank() {
        FmpConfig cfg = new FmpConfig();
        cfg.apiKey = "";
        cfg.baseUrl = "https://financialmodelingprep.com/api/v3";

        FmpMarketDataProvider provider = new FmpMarketDataProvider(cfg);
        List<PricePoint> result = provider.fetchDailyPrices("AAPL", 30);

        assertThat(result).isEmpty();
    }

    @Test
    void returnsEmptyOnNetworkError() {
        FmpConfig cfg = new FmpConfig();
        cfg.apiKey = "test-key";
        cfg.baseUrl = "http://localhost:19999"; // nothing listening here

        FmpMarketDataProvider provider = new FmpMarketDataProvider(cfg);
        List<PricePoint> result = provider.fetchDailyPrices("AAPL", 30);

        assertThat(result).isEmpty();
    }
}
```

- [ ] **Step 5: Run the test — must pass**

```bash
mvn -B test -pl . -Dtest=FmpMarketDataProviderTest -q
# Expected: Tests run: 2, Failures: 0, Errors: 0
```

- [ ] **Step 6: Commit**

```bash
git add src/main/java/com/finrisk/marketdata/fmp/ \
        src/main/resources/application.yml \
        src/test/java/com/finrisk/marketdata/
git commit -m "feat: FmpMarketDataProvider — fetches daily prices from FinancialModelingPrep"
```

---

### Task 4: Add `upsertForDate` to AssetPriceHistoryDao

**Files:**
- Modify: `src/main/java/com/finrisk/dao/AssetPriceHistoryDao.java`
- Modify: `src/main/java/com/finrisk/dao/impl/AssetPriceHistoryDaoJdbc.java`

**Interfaces:**
- Produces: `AssetPriceHistoryDao.upsertForDate(long assetId, LocalDate date, BigDecimal price): void`

Using SQL Server MERGE: if a row already exists for `(asset_id, date)` it updates the price; otherwise it inserts. Uses `CAST(recorded_at AS DATE)` to match on calendar date regardless of time.

- [ ] **Step 1: Add method to `AssetPriceHistoryDao` interface**

Open `src/main/java/com/finrisk/dao/AssetPriceHistoryDao.java`. Add after the existing `insert` signature:

```java
import java.time.LocalDate;

// ...existing methods...

void upsertForDate(long assetId, LocalDate date, BigDecimal price);
```

(Also add `import java.time.LocalDate;` if not already present.)

- [ ] **Step 2: Implement in `AssetPriceHistoryDaoJdbc`**

Open `src/main/java/com/finrisk/dao/impl/AssetPriceHistoryDaoJdbc.java`. Add after the existing `insert` method:

```java
import java.time.LocalDate;
import java.sql.Date;

@Override
public void upsertForDate(long assetId, LocalDate date, BigDecimal price) {
    Db.exec(
            """
            MERGE dbo.asset_price_history AS tgt
            USING (VALUES (?, ?, ?)) AS src (asset_id, price, price_date)
              ON tgt.asset_id = src.asset_id
             AND CAST(tgt.recorded_at AS DATE) = src.price_date
            WHEN MATCHED THEN
                UPDATE SET tgt.price = src.price
            WHEN NOT MATCHED THEN
                INSERT (asset_id, price, recorded_at)
                VALUES (src.asset_id, src.price, CAST(src.price_date AS DATETIME2));
            """,
            assetId,
            price,
            Date.valueOf(date));
}
```

- [ ] **Step 3: Verify compilation**

```bash
mvn -B compile -q
# Expected: BUILD SUCCESS
```

- [ ] **Step 4: Commit**

```bash
git add src/main/java/com/finrisk/dao/
git commit -m "feat: add upsertForDate to AssetPriceHistoryDao using SQL Server MERGE"
```

---

### Task 5: MarketDataService + tests

**Files:**
- Create: `src/main/java/com/finrisk/service/MarketDataService.java`
- Create: `src/test/java/com/finrisk/service/MarketDataServiceTest.java`

**Interfaces:**
- Consumes: `MarketDataProvider.fetchDailyPrices(String, int)`, `AssetDao.findById(long)`, `AssetPriceHistoryDao.upsertForDate(long, LocalDate, BigDecimal)`
- Produces: `MarketDataService.syncPrices(long assetId, int days): int` — returns number of price points synced

- [ ] **Step 1: Write the failing test first**

Create `src/test/java/com/finrisk/service/MarketDataServiceTest.java`:

```java
package com.finrisk.service;

import com.finrisk.dao.AssetDao;
import com.finrisk.dao.AssetPriceHistoryDao;
import com.finrisk.exception.AssetNotFoundException;
import com.finrisk.marketdata.MarketDataProvider;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.model.Asset;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class MarketDataServiceTest {

    @Mock MarketDataProvider provider;
    @Mock AssetDao assetDao;
    @Mock AssetPriceHistoryDao priceHistoryDao;
    @Mock Asset asset;

    MarketDataService service;

    @BeforeEach
    void setUp() {
        service = new MarketDataService(provider, assetDao, priceHistoryDao);
    }

    @Test
    void syncPrices_throwsWhenAssetNotFound() {
        when(assetDao.findById(99L)).thenReturn(null);

        assertThatThrownBy(() -> service.syncPrices(99L, 30))
                .isInstanceOf(AssetNotFoundException.class);
    }

    @Test
    void syncPrices_upsertsAllReturnedPoints() {
        when(assetDao.findById(1L)).thenReturn(asset);
        when(asset.symbol()).thenReturn("AAPL");
        List<PricePoint> points = List.of(
                new PricePoint(LocalDate.of(2024, 6, 27), new BigDecimal("180.00")),
                new PricePoint(LocalDate.of(2024, 6, 28), new BigDecimal("182.50"))
        );
        when(provider.fetchDailyPrices("AAPL", 30)).thenReturn(points);

        int synced = service.syncPrices(1L, 30);

        assertThat(synced).isEqualTo(2);
        verify(priceHistoryDao).upsertForDate(1L, LocalDate.of(2024, 6, 27), new BigDecimal("180.00"));
        verify(priceHistoryDao).upsertForDate(1L, LocalDate.of(2024, 6, 28), new BigDecimal("182.50"));
    }

    @Test
    void syncPrices_returnsZeroWhenProviderReturnsEmpty() {
        when(assetDao.findById(1L)).thenReturn(asset);
        when(asset.symbol()).thenReturn("UNKNOWN");
        when(provider.fetchDailyPrices("UNKNOWN", 30)).thenReturn(List.of());

        int synced = service.syncPrices(1L, 30);

        assertThat(synced).isEqualTo(0);
        verifyNoInteractions(priceHistoryDao);
    }
}
```

- [ ] **Step 2: Run test — expect compilation failure**

```bash
mvn -B test -Dtest=MarketDataServiceTest -q 2>&1 | tail -5
# Expected: error: cannot find symbol (MarketDataService does not exist yet)
```

- [ ] **Step 3: Create `MarketDataService.java`**

```java
package com.finrisk.service;

import com.finrisk.dao.AssetDao;
import com.finrisk.dao.AssetPriceHistoryDao;
import com.finrisk.exception.AssetNotFoundException;
import com.finrisk.marketdata.MarketDataProvider;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.model.Asset;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class MarketDataService {

    private final MarketDataProvider provider;
    private final AssetDao assetDao;
    private final AssetPriceHistoryDao priceHistoryDao;

    public MarketDataService(
            MarketDataProvider provider,
            AssetDao assetDao,
            AssetPriceHistoryDao priceHistoryDao) {
        this.provider = provider;
        this.assetDao = assetDao;
        this.priceHistoryDao = priceHistoryDao;
    }

    public int syncPrices(long assetId, int days) {
        Asset asset = assetDao.findById(assetId);
        if (asset == null) {
            throw new AssetNotFoundException("Asset not found: " + assetId);
        }
        List<PricePoint> points = provider.fetchDailyPrices(asset.symbol(), days);
        for (PricePoint p : points) {
            priceHistoryDao.upsertForDate(assetId, p.date(), p.close());
        }
        return points.size();
    }
}
```

- [ ] **Step 4: Run test — must pass**

```bash
mvn -B test -Dtest=MarketDataServiceTest -q
# Expected: Tests run: 3, Failures: 0, Errors: 0
```

- [ ] **Step 5: Commit**

```bash
git add src/main/java/com/finrisk/service/MarketDataService.java \
        src/test/java/com/finrisk/service/MarketDataServiceTest.java
git commit -m "feat: MarketDataService — sync asset prices from market data provider (TDD)"
```

---

### Task 6: Wire sync endpoint in AssetController

**Files:**
- Modify: `src/main/java/com/finrisk/controller/AssetController.java`

**Interfaces:**
- Consumes: `MarketDataService.syncPrices(long assetId, int days): int`
- Produces: `POST /api/v1/assets/{id}/sync-prices?days=30` → `{ "synced": N }` with HTTP 200

- [ ] **Step 1: Open AssetController and inject MarketDataService**

Find the constructor in `AssetController.java`. Add `MarketDataService marketDataService` as a parameter and store it in a field:

```java
// Add field
private final MarketDataService marketDataService;

// Update constructor — add parameter and assignment
public AssetController(AssetService assetService, MarketDataService marketDataService) {
    this.assetService = assetService;
    this.marketDataService = marketDataService;
}
```

(Add `import com.finrisk.service.MarketDataService;` at the top.)

- [ ] **Step 2: Add the sync endpoint method**

Inside `AssetController`, add after the price-history endpoint:

```java
import org.springframework.web.bind.annotation.RequestParam;
import java.util.Map;

@PostMapping("/{id}/sync-prices")
public ResponseEntity<Map<String, Integer>> syncPrices(
        @PathVariable long id,
        @RequestParam(defaultValue = "30") int days) {
    int synced = marketDataService.syncPrices(id, days);
    return ResponseEntity.ok(Map.of("synced", synced));
}
```

- [ ] **Step 3: Verify full compile + existing unit tests still pass**

```bash
mvn -B test -q
# Expected: BUILD SUCCESS, no regressions
```

- [ ] **Step 4: Smoke-test against running stack (optional — requires FMP_API_KEY)**

```bash
set -a && source .env && set +a
make up
bash db/scripts/apply-migrations.sh FinRiskDB
bash db/scripts/seed.sh FinRiskDB
# SEED00001 has symbol SEED00001 — FMP won't know it, returns 0
curl -s -X POST "http://localhost:18080/api/v1/assets/1/sync-prices?days=30"
# Expected: {"synced":0}  (unless FMP_API_KEY is set and symbol is real)
```

- [ ] **Step 5: Commit**

```bash
git add src/main/java/com/finrisk/controller/AssetController.java
git commit -m "feat: POST /api/v1/assets/{id}/sync-prices — triggers market data sync"
```

---

### Task 7: Full test run + final cleanup

- [ ] **Step 1: Run all unit tests**

```bash
mvn -B test -q
# Expected: BUILD SUCCESS
```

- [ ] **Step 2: Run integration tests (requires Docker + SQL Server running)**

```bash
set -a && source .env && set +a
docker compose up -d sqlserver
bash db/scripts/apply-migrations.sh FinRiskDB_Test
mvn -B verify -q
# Expected: BUILD SUCCESS
```

- [ ] **Step 3: Verify docker-compose no longer references finrisk-web**

```bash
grep -i "finrisk-web" docker-compose.yml && echo "FOUND - fix it" || echo "OK"
# Expected: OK
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: final cleanup — all tests green, finrisk-web fully removed"
```

---

## Self-Review Checklist

- [x] `finrisk-web/` deleted, docker-compose service removed, pom.xml cleaned (Task 1)
- [x] `MarketDataProvider` interface in `com.finrisk.marketdata` — not tied to FMP (Task 2)
- [x] `FmpMarketDataProvider` self-contained in `com.finrisk.marketdata.fmp` — new provider = new class, zero service changes (Task 3)
- [x] Empty API key → empty list returned, no exceptions thrown (Task 3, Step 2)
- [x] `upsertForDate` prevents duplicate daily prices via SQL Server MERGE (Task 4)
- [x] `MarketDataService` tested with mocked provider — TDD green (Task 5)
- [x] Sync endpoint wired at `POST /api/v1/assets/{id}/sync-prices` (Task 6)
- [x] No new Maven dependencies added
