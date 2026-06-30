# Risk Management MS — Beta, Sector Exposure, Diversification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `volatility-ms` → `risk-management-ms` and add three new analytical endpoints: portfolio beta vs. SPY, sector exposure breakdown, and a HHI-based diversification score.

**Architecture:** Three new Spring services (`BetaService`, `SectorExposureService`, `DiversificationService`) follow the exact pattern of `RiskService` — constructor-injected DAO/provider dependencies, unit-tested with Mockito, wired into `PortfolioController` as new `GET` endpoints. `MarketDataProvider` is extended with a `fetchProfile` method to supply sector data; `FmpMarketDataProvider` implements it via FMP `/v3/profile/{symbol}`.

**Tech Stack:** Java 21, Spring Boot 3.3.6, Maven, JUnit 5, Mockito, AssertJ. Market data from FinancialModelingPrep (existing `FmpMarketDataProvider`). No new Maven dependencies required.

## Global Constraints

- Package root: `com.finrisk`
- Java 21 features allowed (records, sealed types, `var`, text blocks)
- No ORM — raw JDBC only (existing `AssetPriceHistoryDao`, `PortfolioDao`)
- All new services must compile with `mvn -B test -DskipTests` and pass `mvn -B test`
- Market benchmark for beta: ticker `"SPY"` (S&P 500 ETF)
- Beta fallback when insufficient data (< 5 price points): `1.0`
- HHI formula: `sum(weight_i²)` where `weight_i = holding.currentValue() / totalHoldingsValue`
- Diversification score: `(1 − HHI) × 100`, rounded to 2 decimal places
- `fetchProfile` returns `new CompanyProfile(symbol, "Unknown", "Unknown", symbol)` on any error (never throws)
- All working directory commands below assume CWD = `risk-management-ms/` (i.e. after the rename in Task 1)

---

## File Map

| Status | File | Purpose |
|--------|------|---------|
| rename | `volatility-ms/` → `risk-management-ms/` | Directory rename |
| modify | `pom.xml` | artifactId + name |
| modify | `src/main/resources/application.yml` | spring.application.name |
| modify | `docker-compose.yml` | service + container name |
| create | `src/main/java/com/finrisk/marketdata/CompanyProfile.java` | Record: symbol, sector, industry, companyName |
| modify | `src/main/java/com/finrisk/marketdata/MarketDataProvider.java` | Add `fetchProfile` method |
| modify | `src/main/java/com/finrisk/marketdata/fmp/FmpMarketDataProvider.java` | Implement `fetchProfile` via FMP `/v3/profile/{symbol}` |
| modify | `src/test/java/com/finrisk/marketdata/fmp/FmpMarketDataProviderTest.java` | Add `fetchProfile` tests |
| create | `src/main/java/com/finrisk/dto/response/HoldingBeta.java` | Record: assetId, symbol, beta, weight |
| create | `src/main/java/com/finrisk/dto/response/BetaResponse.java` | Record: accountId, portfolioBeta, benchmark, holdings |
| create | `src/main/java/com/finrisk/service/BetaService.java` | Compute portfolio beta vs SPY |
| create | `src/main/java/com/finrisk/dto/response/SectorAllocation.java` | Record: sector, weight, value, symbols |
| create | `src/main/java/com/finrisk/dto/response/SectorExposureResponse.java` | Record: accountId, sectors |
| create | `src/main/java/com/finrisk/service/SectorExposureService.java` | Group holdings by sector, compute weights |
| create | `src/main/java/com/finrisk/dto/response/AssetTypeAllocation.java` | Record: assetType, weight, value |
| create | `src/main/java/com/finrisk/dto/response/DiversificationResponse.java` | Record: accountId, score, hhiIndex, counts, breakdown |
| create | `src/main/java/com/finrisk/service/DiversificationService.java` | HHI score + asset type breakdown |
| modify | `src/main/java/com/finrisk/controller/PortfolioController.java` | Add /beta, /sector-exposure, /diversification |
| create | `src/test/java/com/finrisk/service/BetaServiceTest.java` | Unit tests |
| create | `src/test/java/com/finrisk/service/SectorExposureServiceTest.java` | Unit tests |
| create | `src/test/java/com/finrisk/service/DiversificationServiceTest.java` | Unit tests |

---

### Task 1: Rename directory and update internal references

**Files:**
- Shell: `mv volatility-ms risk-management-ms`
- Modify: `risk-management-ms/pom.xml`
- Modify: `risk-management-ms/src/main/resources/application.yml`
- Modify: `risk-management-ms/docker-compose.yml`

**Interfaces:**
- Produces: `risk-management-ms/` directory with updated metadata; all subsequent tasks work from this path

- [ ] **Step 1: Rename the directory**

Run from `financeKit/`:
```bash
mv volatility-ms risk-management-ms
```

- [ ] **Step 2: Update pom.xml**

In `risk-management-ms/pom.xml`, change:
```xml
  <artifactId>finrisk-api</artifactId>
  <version>0.1.0-SNAPSHOT</version>
  <name>FinRisk API</name>
```
to:
```xml
  <artifactId>risk-management-api</artifactId>
  <version>0.1.0-SNAPSHOT</version>
  <name>Risk Management API</name>
```

- [ ] **Step 3: Update application.yml**

In `risk-management-ms/src/main/resources/application.yml`, change:
```yaml
spring:
  application:
    name: finrisk-api
```
to:
```yaml
spring:
  application:
    name: risk-management-api
```

- [ ] **Step 4: Update docker-compose.yml**

In `risk-management-ms/docker-compose.yml`, change the service block:
```yaml
  finrisk-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: finrisk-api
```
to:
```yaml
  risk-management-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: risk-management-api
```

Also update any `depends_on:` blocks in other services that reference `finrisk-api` → `risk-management-api`.

- [ ] **Step 5: Verify build compiles**

Run from `risk-management-ms/`:
```bash
mvn -B test -DskipTests
```
Expected: `BUILD SUCCESS`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: rename volatility-ms to risk-management-ms"
```

---

### Task 2: Extend MarketDataProvider with `fetchProfile`

**Files:**
- Create: `src/main/java/com/finrisk/marketdata/CompanyProfile.java`
- Modify: `src/main/java/com/finrisk/marketdata/MarketDataProvider.java`
- Modify: `src/main/java/com/finrisk/marketdata/fmp/FmpMarketDataProvider.java`
- Modify: `src/test/java/com/finrisk/marketdata/fmp/FmpMarketDataProviderTest.java`

**Interfaces:**
- Consumes: existing `FmpConfig` (apiKey, baseUrl), existing `HttpClient` + `ObjectMapper` in `FmpMarketDataProvider`
- Produces: `MarketDataProvider.fetchProfile(String symbol)` → `CompanyProfile(symbol, sector, industry, companyName)`, never throws

- [ ] **Step 1: Write the failing test**

Add to `src/test/java/com/finrisk/marketdata/fmp/FmpMarketDataProviderTest.java`:

```java
@Test
void fetchProfile_returnsDefaultWhenApiKeyBlank() {
    FmpConfig cfg = new FmpConfig();
    cfg.setApiKey("");
    cfg.setBaseUrl("https://financialmodelingprep.com/api/v3");

    FmpMarketDataProvider provider = new FmpMarketDataProvider(cfg);
    CompanyProfile profile = provider.fetchProfile("AAPL");

    assertThat(profile.symbol()).isEqualTo("AAPL");
    assertThat(profile.sector()).isEqualTo("Unknown");
}

@Test
void fetchProfile_returnsDefaultOnNetworkError() {
    FmpConfig cfg = new FmpConfig();
    cfg.setApiKey("test-key");
    cfg.setBaseUrl("http://localhost:19999");

    FmpMarketDataProvider provider = new FmpMarketDataProvider(cfg);
    CompanyProfile profile = provider.fetchProfile("AAPL");

    assertThat(profile.symbol()).isEqualTo("AAPL");
    assertThat(profile.sector()).isEqualTo("Unknown");
}
```

Add import at top of the file:
```java
import com.finrisk.marketdata.CompanyProfile;
```

- [ ] **Step 2: Run test to verify it fails**

```bash
mvn -B test -pl . -Dtest=FmpMarketDataProviderTest
```
Expected: COMPILATION ERROR — `CompanyProfile` does not exist

- [ ] **Step 3: Create CompanyProfile record**

Create `src/main/java/com/finrisk/marketdata/CompanyProfile.java`:
```java
package com.finrisk.marketdata;

public record CompanyProfile(
        String symbol,
        String sector,
        String industry,
        String companyName) {}
```

- [ ] **Step 4: Add `fetchProfile` to MarketDataProvider interface**

Replace the entire content of `src/main/java/com/finrisk/marketdata/MarketDataProvider.java`:
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

    /**
     * Returns company profile for {@code symbol}. Never throws; returns a
     * default profile with sector/industry = "Unknown" on any error.
     */
    CompanyProfile fetchProfile(String symbol);
}
```

- [ ] **Step 5: Implement `fetchProfile` in FmpMarketDataProvider**

Add to `src/main/java/com/finrisk/marketdata/fmp/FmpMarketDataProvider.java`, after the `fetchDailyPrices` method:

```java
@Override
public CompanyProfile fetchProfile(String symbol) {
    CompanyProfile unknown = new CompanyProfile(symbol, "Unknown", "Unknown", symbol);
    if (config.getApiKey() == null || config.getApiKey().isBlank()) {
        return unknown;
    }
    try {
        String url = "%s/profile/%s?apikey=%s"
                .formatted(config.getBaseUrl(), symbol, config.getApiKey());
        HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                .GET()
                .build();
        HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
        if (resp.statusCode() != 200) {
            log.warn("FMP profile returned HTTP {} for symbol {}", resp.statusCode(), symbol);
            return unknown;
        }
        JsonNode root = mapper.readTree(resp.body());
        if (!root.isArray() || root.isEmpty()) {
            return unknown;
        }
        JsonNode p = root.get(0);
        return new CompanyProfile(
                symbol,
                p.path("sector").asText("Unknown"),
                p.path("industry").asText("Unknown"),
                p.path("companyName").asText(symbol));
    } catch (Exception e) {
        log.warn("FMP fetchProfile failed for symbol {}: {}", symbol, e.getMessage());
        return unknown;
    }
}
```

Also add `import com.finrisk.marketdata.CompanyProfile;` to the imports in `FmpMarketDataProvider.java`.

- [ ] **Step 6: Run tests**

```bash
mvn -B test -pl . -Dtest=FmpMarketDataProviderTest
```
Expected: 4 tests pass (2 existing + 2 new)

- [ ] **Step 7: Commit**

```bash
git add src/main/java/com/finrisk/marketdata/CompanyProfile.java \
        src/main/java/com/finrisk/marketdata/MarketDataProvider.java \
        src/main/java/com/finrisk/marketdata/fmp/FmpMarketDataProvider.java \
        src/test/java/com/finrisk/marketdata/fmp/FmpMarketDataProviderTest.java
git commit -m "feat: extend MarketDataProvider with fetchProfile for sector data"
```

---

### Task 3: Beta service and endpoint

**Files:**
- Create: `src/main/java/com/finrisk/dto/response/HoldingBeta.java`
- Create: `src/main/java/com/finrisk/dto/response/BetaResponse.java`
- Create: `src/main/java/com/finrisk/service/BetaService.java`
- Modify: `src/main/java/com/finrisk/controller/PortfolioController.java`
- Create: `src/test/java/com/finrisk/service/BetaServiceTest.java`

**Interfaces:**
- Consumes:
  - `PortfolioDao.cashBalance(long accountId)` → `Optional<BigDecimal>`
  - `PortfolioDao.holdings(long accountId)` → `List<Holding>` (each Holding has `assetId`, `symbol`, `currentValue`, `assetType`)
  - `AssetPriceHistoryDao.latestPrices(long assetId, int limit)` → `List<BigDecimal>` newest-first
  - `MarketDataProvider.fetchDailyPrices("SPY", 90)` → `List<PricePoint>` newest-first
  - `AccountNotFoundException` from `com.finrisk.exception`
- Produces:
  - `BetaService.computeBeta(long accountId)` → `BetaResponse`
  - `GET /api/v1/accounts/{accountId}/beta` → JSON `BetaResponse`

**Beta math:**
```
logReturns[i] = ln(price[i+1] / price[i])  (over chronological ascending series)
cov(a, m)     = Σ (r_a[i] − mean_a)(r_m[i] − mean_m) / (n−1)
var(m)        = Σ (r_m[i] − mean_m)² / (n−1)
beta          = cov(a, m) / var(m)
fallback      = 1.0  when n < 5 or var(m) == 0
portfolioBeta = Σ weight_i × beta_i
```

- [ ] **Step 1: Write the failing tests**

Create `src/test/java/com/finrisk/service/BetaServiceTest.java`:

```java
package com.finrisk.service;

import com.finrisk.dao.AssetPriceHistoryDao;
import com.finrisk.dao.PortfolioDao;
import com.finrisk.dto.response.BetaResponse;
import com.finrisk.dto.response.Holding;
import com.finrisk.exception.AccountNotFoundException;
import com.finrisk.marketdata.MarketDataProvider;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.model.AssetType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class BetaServiceTest {

    @Mock PortfolioDao portfolioDao;
    @Mock AssetPriceHistoryDao priceHistoryDao;
    @Mock MarketDataProvider marketDataProvider;

    BetaService service;

    @BeforeEach
    void setUp() {
        service = new BetaService(portfolioDao, priceHistoryDao, marketDataProvider);
    }

    @Test
    void throwsWhenAccountNotFound() {
        when(portfolioDao.cashBalance(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.computeBeta(99L))
                .isInstanceOf(AccountNotFoundException.class);
    }

    @Test
    void returnsPortfolioBetaOneWhenNoHoldings() {
        when(portfolioDao.cashBalance(1L)).thenReturn(Optional.of(BigDecimal.valueOf(1000)));
        when(portfolioDao.holdings(1L)).thenReturn(List.of());

        BetaResponse response = service.computeBeta(1L);

        assertThat(response.accountId()).isEqualTo(1L);
        assertThat(response.portfolioBeta()).isEqualTo(1.0);
        assertThat(response.benchmark()).isEqualTo("SPY");
        assertThat(response.holdings()).isEmpty();
    }

    @Test
    void usesFallbackBetaWhenInsufficientPriceHistory() {
        Holding h = new Holding(1L, "AAPL", "Apple", AssetType.STOCK, 10,
                BigDecimal.valueOf(180), BigDecimal.valueOf(1800));
        when(portfolioDao.cashBalance(1L)).thenReturn(Optional.of(BigDecimal.ZERO));
        when(portfolioDao.holdings(1L)).thenReturn(List.of(h));
        when(priceHistoryDao.latestPrices(1L, 90)).thenReturn(List.of(BigDecimal.valueOf(180)));
        when(marketDataProvider.fetchDailyPrices("SPY", 90)).thenReturn(List.of());

        BetaResponse response = service.computeBeta(1L);

        assertThat(response.holdings()).hasSize(1);
        assertThat(response.holdings().get(0).beta()).isEqualTo(1.0);
    }

    @Test
    void computesNonTrivialBetaFromPriceSeries() {
        // Asset prices move exactly 2× the SPY moves → beta ≈ 2.0
        List<BigDecimal> spyPrices = List.of(
                bd("100"), bd("102"), bd("101"), bd("103"), bd("105"),
                bd("104"), bd("106"), bd("108"), bd("107"), bd("109")
        );
        // Reverse to newest-first (as latestPrices / fetchDailyPrices return)
        List<BigDecimal> spyNewest = spyPrices.reversed();
        List<BigDecimal> assetPrices = List.of(
                bd("200"), bd("204"), bd("202"), bd("206"), bd("210"),
                bd("208"), bd("212"), bd("216"), bd("214"), bd("218")
        );
        List<BigDecimal> assetNewest = assetPrices.reversed();

        // SPY as PricePoints
        List<PricePoint> spyPoints = new java.util.ArrayList<>();
        for (int i = 0; i < spyNewest.size(); i++) {
            spyPoints.add(new PricePoint(LocalDate.now().minusDays(i), spyNewest.get(i)));
        }

        Holding h = new Holding(1L, "AAPL", "Apple", AssetType.STOCK, 10,
                bd("218"), bd("2180"));
        when(portfolioDao.cashBalance(1L)).thenReturn(Optional.of(BigDecimal.ZERO));
        when(portfolioDao.holdings(1L)).thenReturn(List.of(h));
        when(priceHistoryDao.latestPrices(1L, 90)).thenReturn(assetNewest);
        when(marketDataProvider.fetchDailyPrices("SPY", 90)).thenReturn(spyPoints);

        BetaResponse response = service.computeBeta(1L);

        assertThat(response.holdings().get(0).beta()).isCloseTo(2.0, org.assertj.core.data.Offset.offset(0.01));
        assertThat(response.portfolioBeta()).isCloseTo(2.0, org.assertj.core.data.Offset.offset(0.01));
    }

    private static BigDecimal bd(String v) { return new BigDecimal(v); }
}
```

- [ ] **Step 2: Run to verify they fail**

```bash
mvn -B test -pl . -Dtest=BetaServiceTest
```
Expected: COMPILATION ERROR — `BetaService`, `BetaResponse`, `HoldingBeta` do not exist

- [ ] **Step 3: Create DTOs**

Create `src/main/java/com/finrisk/dto/response/HoldingBeta.java`:
```java
package com.finrisk.dto.response;

public record HoldingBeta(long assetId, String symbol, double beta, double weight) {}
```

Create `src/main/java/com/finrisk/dto/response/BetaResponse.java`:
```java
package com.finrisk.dto.response;

import java.util.List;

public record BetaResponse(
        long accountId,
        double portfolioBeta,
        String benchmark,
        List<HoldingBeta> holdings) {}
```

- [ ] **Step 4: Create BetaService**

Create `src/main/java/com/finrisk/service/BetaService.java`:
```java
package com.finrisk.service;

import com.finrisk.dao.AssetPriceHistoryDao;
import com.finrisk.dao.PortfolioDao;
import com.finrisk.dto.response.BetaResponse;
import com.finrisk.dto.response.Holding;
import com.finrisk.dto.response.HoldingBeta;
import com.finrisk.exception.AccountNotFoundException;
import com.finrisk.marketdata.MarketDataProvider;
import com.finrisk.marketdata.PricePoint;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

@Service
public class BetaService {

    private static final String BENCHMARK = "SPY";
    private static final int PRICE_DAYS = 90;
    private static final int MIN_SAMPLES = 5;

    private final PortfolioDao portfolioDao;
    private final AssetPriceHistoryDao priceHistoryDao;
    private final MarketDataProvider marketDataProvider;

    public BetaService(
            PortfolioDao portfolioDao,
            AssetPriceHistoryDao priceHistoryDao,
            MarketDataProvider marketDataProvider) {
        this.portfolioDao = portfolioDao;
        this.priceHistoryDao = priceHistoryDao;
        this.marketDataProvider = marketDataProvider;
    }

    public BetaResponse computeBeta(long accountId) {
        if (portfolioDao.cashBalance(accountId).isEmpty()) {
            throw new AccountNotFoundException("Account not found");
        }

        List<Holding> holdings = portfolioDao.holdings(accountId);
        if (holdings.isEmpty()) {
            return new BetaResponse(accountId, 1.0, BENCHMARK, List.of());
        }

        // Fetch SPY benchmark prices, reverse to chronological ascending
        List<PricePoint> spyPoints = marketDataProvider.fetchDailyPrices(BENCHMARK, PRICE_DAYS);
        List<Double> spyPrices = spyPoints.stream()
                .map(p -> p.close().doubleValue())
                .toList()
                .reversed();

        BigDecimal totalValue = holdings.stream()
                .map(Holding::currentValue)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        List<HoldingBeta> holdingBetas = new ArrayList<>();
        double portfolioBeta = 0.0;

        for (Holding h : holdings) {
            // Fetch asset prices, reverse to chronological ascending
            List<Double> assetPrices = priceHistoryDao.latestPrices(h.assetId(), PRICE_DAYS)
                    .stream().map(BigDecimal::doubleValue).toList().reversed();

            double beta = computeHoldingBeta(assetPrices, spyPrices);

            double weight = totalValue.compareTo(BigDecimal.ZERO) == 0 ? 0.0
                    : h.currentValue().divide(totalValue, 8, RoundingMode.HALF_UP).doubleValue();

            holdingBetas.add(new HoldingBeta(h.assetId(), h.symbol(), beta, weight));
            portfolioBeta += weight * beta;
        }

        return new BetaResponse(accountId, portfolioBeta, BENCHMARK, holdingBetas);
    }

    private double computeHoldingBeta(List<Double> assetPrices, List<Double> spyPrices) {
        int n = Math.min(assetPrices.size(), spyPrices.size()) - 1;
        if (n < MIN_SAMPLES) return 1.0;

        double[] rA = logReturns(assetPrices.subList(0, n + 1));
        double[] rM = logReturns(spyPrices.subList(0, n + 1));
        int len = Math.min(rA.length, rM.length);

        double meanA = mean(rA, len);
        double meanM = mean(rM, len);

        double cov = 0.0, varM = 0.0;
        for (int i = 0; i < len; i++) {
            cov  += (rA[i] - meanA) * (rM[i] - meanM);
            varM += (rM[i] - meanM) * (rM[i] - meanM);
        }
        if (len <= 1 || varM == 0.0) return 1.0;
        return (cov / (len - 1)) / (varM / (len - 1));
    }

    private double[] logReturns(List<Double> prices) {
        double[] r = new double[prices.size() - 1];
        for (int i = 1; i < prices.size(); i++) {
            r[i - 1] = Math.log(prices.get(i) / prices.get(i - 1));
        }
        return r;
    }

    private double mean(double[] arr, int len) {
        double sum = 0;
        for (int i = 0; i < len; i++) sum += arr[i];
        return sum / len;
    }
}
```

- [ ] **Step 5: Run tests**

```bash
mvn -B test -pl . -Dtest=BetaServiceTest
```
Expected: 4 tests pass

- [ ] **Step 6: Add endpoint to PortfolioController**

In `src/main/java/com/finrisk/controller/PortfolioController.java`:

Add to constructor parameters:
```java
private final BetaService betaService;
```

Add `BetaService betaService` to the constructor signature and body. Also add import:
```java
import com.finrisk.dto.response.BetaResponse;
import com.finrisk.service.BetaService;
```

Add the endpoint method:
```java
@GetMapping("/beta")
public BetaResponse beta(@PathVariable long accountId) {
    return betaService.computeBeta(accountId);
}
```

The full updated controller:
```java
package com.finrisk.controller;

import com.finrisk.dto.response.BetaResponse;
import com.finrisk.dto.response.PortfolioResponse;
import com.finrisk.dto.response.ProfitLossResponse;
import com.finrisk.dto.response.RiskScoreResponse;
import com.finrisk.service.BetaService;
import com.finrisk.service.PortfolioService;
import com.finrisk.service.ProfitLossService;
import com.finrisk.service.RiskService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/accounts/{accountId}")
public class PortfolioController {

    private final PortfolioService portfolioService;
    private final ProfitLossService profitLossService;
    private final RiskService riskService;
    private final BetaService betaService;

    public PortfolioController(
            PortfolioService portfolioService,
            ProfitLossService profitLossService,
            RiskService riskService,
            BetaService betaService) {
        this.portfolioService = portfolioService;
        this.profitLossService = profitLossService;
        this.riskService = riskService;
        this.betaService = betaService;
    }

    @GetMapping("/portfolio")
    public PortfolioResponse portfolio(@PathVariable long accountId) {
        return portfolioService.getPortfolio(accountId);
    }

    @GetMapping("/profit-loss")
    public ProfitLossResponse profitLoss(@PathVariable long accountId) {
        return profitLossService.getProfitLoss(accountId);
    }

    @GetMapping("/risk")
    public RiskScoreResponse risk(@PathVariable long accountId) {
        return riskService.computeRisk(accountId);
    }

    @GetMapping("/beta")
    public BetaResponse beta(@PathVariable long accountId) {
        return betaService.computeBeta(accountId);
    }
}
```

- [ ] **Step 7: Full test run**

```bash
mvn -B test
```
Expected: BUILD SUCCESS, all existing tests + BetaServiceTest pass

- [ ] **Step 8: Commit**

```bash
git add src/main/java/com/finrisk/dto/response/HoldingBeta.java \
        src/main/java/com/finrisk/dto/response/BetaResponse.java \
        src/main/java/com/finrisk/service/BetaService.java \
        src/main/java/com/finrisk/controller/PortfolioController.java \
        src/test/java/com/finrisk/service/BetaServiceTest.java
git commit -m "feat: add portfolio beta vs SPY endpoint GET /api/v1/accounts/{id}/beta"
```

---

### Task 4: Sector exposure service and endpoint

**Files:**
- Create: `src/main/java/com/finrisk/dto/response/SectorAllocation.java`
- Create: `src/main/java/com/finrisk/dto/response/SectorExposureResponse.java`
- Create: `src/main/java/com/finrisk/service/SectorExposureService.java`
- Modify: `src/main/java/com/finrisk/controller/PortfolioController.java`
- Create: `src/test/java/com/finrisk/service/SectorExposureServiceTest.java`

**Interfaces:**
- Consumes:
  - `PortfolioDao.cashBalance(long)` → `Optional<BigDecimal>`
  - `PortfolioDao.holdings(long)` → `List<Holding>`
  - `MarketDataProvider.fetchProfile(String symbol)` → `CompanyProfile`
  - `AccountNotFoundException`
- Produces:
  - `SectorExposureService.computeSectorExposure(long accountId)` → `SectorExposureResponse`
  - `GET /api/v1/accounts/{accountId}/sector-exposure` → JSON `SectorExposureResponse`

**Logic:** For each holding, call `fetchProfile(symbol)` to get sector. Group holdings by sector, sum `currentValue` per group, compute `weight = sectorValue / totalHoldingsValue`, collect symbols per sector. Sort result by `weight` descending.

- [ ] **Step 1: Write failing tests**

Create `src/test/java/com/finrisk/service/SectorExposureServiceTest.java`:

```java
package com.finrisk.service;

import com.finrisk.dao.PortfolioDao;
import com.finrisk.dto.response.Holding;
import com.finrisk.dto.response.SectorAllocation;
import com.finrisk.dto.response.SectorExposureResponse;
import com.finrisk.exception.AccountNotFoundException;
import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.MarketDataProvider;
import com.finrisk.model.AssetType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class SectorExposureServiceTest {

    @Mock PortfolioDao portfolioDao;
    @Mock MarketDataProvider marketDataProvider;

    SectorExposureService service;

    @BeforeEach
    void setUp() {
        service = new SectorExposureService(portfolioDao, marketDataProvider);
    }

    @Test
    void throwsWhenAccountNotFound() {
        when(portfolioDao.cashBalance(99L)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.computeSectorExposure(99L))
                .isInstanceOf(AccountNotFoundException.class);
    }

    @Test
    void returnsEmptyWhenNoHoldings() {
        when(portfolioDao.cashBalance(1L)).thenReturn(Optional.of(BigDecimal.valueOf(1000)));
        when(portfolioDao.holdings(1L)).thenReturn(List.of());

        SectorExposureResponse response = service.computeSectorExposure(1L);

        assertThat(response.accountId()).isEqualTo(1L);
        assertThat(response.sectors()).isEmpty();
    }

    @Test
    void groupsHoldingsBySector() {
        Holding aapl = new Holding(1L, "AAPL", "Apple", AssetType.STOCK, 10,
                BigDecimal.valueOf(180), BigDecimal.valueOf(1800));
        Holding msft = new Holding(2L, "MSFT", "Microsoft", AssetType.STOCK, 5,
                BigDecimal.valueOf(300), BigDecimal.valueOf(1500));
        Holding jpm = new Holding(3L, "JPM", "JPMorgan", AssetType.STOCK, 8,
                BigDecimal.valueOf(200), BigDecimal.valueOf(1600));

        when(portfolioDao.cashBalance(1L)).thenReturn(Optional.of(BigDecimal.ZERO));
        when(portfolioDao.holdings(1L)).thenReturn(List.of(aapl, msft, jpm));
        when(marketDataProvider.fetchProfile("AAPL"))
                .thenReturn(new CompanyProfile("AAPL", "Technology", "Software", "Apple Inc."));
        when(marketDataProvider.fetchProfile("MSFT"))
                .thenReturn(new CompanyProfile("MSFT", "Technology", "Software", "Microsoft Corp."));
        when(marketDataProvider.fetchProfile("JPM"))
                .thenReturn(new CompanyProfile("JPM", "Financial Services", "Banks", "JPMorgan Chase"));

        SectorExposureResponse response = service.computeSectorExposure(1L);

        assertThat(response.sectors()).hasSize(2);

        // Sorted by weight descending: Technology (3300/4900 ≈ 67%) > Financial Services (1600/4900 ≈ 33%)
        SectorAllocation tech = response.sectors().get(0);
        assertThat(tech.sector()).isEqualTo("Technology");
        assertThat(tech.symbols()).containsExactlyInAnyOrder("AAPL", "MSFT");
        assertThat(tech.weight()).isGreaterThan(0.5);

        SectorAllocation fin = response.sectors().get(1);
        assertThat(fin.sector()).isEqualTo("Financial Services");
        assertThat(fin.symbols()).containsExactly("JPM");
    }

    @Test
    void weightsAddUpToApproximatelyOne() {
        Holding h1 = new Holding(1L, "AAPL", "Apple", AssetType.STOCK, 10,
                BigDecimal.valueOf(180), BigDecimal.valueOf(1800));
        Holding h2 = new Holding(2L, "JPM", "JPMorgan", AssetType.STOCK, 8,
                BigDecimal.valueOf(200), BigDecimal.valueOf(1600));

        when(portfolioDao.cashBalance(1L)).thenReturn(Optional.of(BigDecimal.ZERO));
        when(portfolioDao.holdings(1L)).thenReturn(List.of(h1, h2));
        when(marketDataProvider.fetchProfile("AAPL"))
                .thenReturn(new CompanyProfile("AAPL", "Technology", "Software", "Apple Inc."));
        when(marketDataProvider.fetchProfile("JPM"))
                .thenReturn(new CompanyProfile("JPM", "Financial Services", "Banks", "JPMorgan Chase"));

        SectorExposureResponse response = service.computeSectorExposure(1L);

        double total = response.sectors().stream().mapToDouble(SectorAllocation::weight).sum();
        assertThat(total).isCloseTo(1.0, org.assertj.core.data.Offset.offset(0.001));
    }
}
```

- [ ] **Step 2: Run to verify they fail**

```bash
mvn -B test -pl . -Dtest=SectorExposureServiceTest
```
Expected: COMPILATION ERROR

- [ ] **Step 3: Create DTOs**

Create `src/main/java/com/finrisk/dto/response/SectorAllocation.java`:
```java
package com.finrisk.dto.response;

import java.math.BigDecimal;
import java.util.List;

public record SectorAllocation(
        String sector,
        double weight,
        BigDecimal value,
        List<String> symbols) {}
```

Create `src/main/java/com/finrisk/dto/response/SectorExposureResponse.java`:
```java
package com.finrisk.dto.response;

import java.util.List;

public record SectorExposureResponse(long accountId, List<SectorAllocation> sectors) {}
```

- [ ] **Step 4: Create SectorExposureService**

Create `src/main/java/com/finrisk/service/SectorExposureService.java`:
```java
package com.finrisk.service;

import com.finrisk.dao.PortfolioDao;
import com.finrisk.dto.response.Holding;
import com.finrisk.dto.response.SectorAllocation;
import com.finrisk.dto.response.SectorExposureResponse;
import com.finrisk.exception.AccountNotFoundException;
import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.MarketDataProvider;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

@Service
public class SectorExposureService {

    private final PortfolioDao portfolioDao;
    private final MarketDataProvider marketDataProvider;

    public SectorExposureService(PortfolioDao portfolioDao, MarketDataProvider marketDataProvider) {
        this.portfolioDao = portfolioDao;
        this.marketDataProvider = marketDataProvider;
    }

    public SectorExposureResponse computeSectorExposure(long accountId) {
        if (portfolioDao.cashBalance(accountId).isEmpty()) {
            throw new AccountNotFoundException("Account not found");
        }

        List<Holding> holdings = portfolioDao.holdings(accountId);
        if (holdings.isEmpty()) {
            return new SectorExposureResponse(accountId, List.of());
        }

        BigDecimal totalValue = holdings.stream()
                .map(Holding::currentValue)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        // sector → { value, symbols }
        Map<String, BigDecimal> sectorValue = new LinkedHashMap<>();
        Map<String, List<String>> sectorSymbols = new LinkedHashMap<>();

        for (Holding h : holdings) {
            CompanyProfile profile = marketDataProvider.fetchProfile(h.symbol());
            String sector = profile.sector();
            sectorValue.merge(sector, h.currentValue(), BigDecimal::add);
            sectorSymbols.computeIfAbsent(sector, k -> new ArrayList<>()).add(h.symbol());
        }

        List<SectorAllocation> allocations = sectorValue.entrySet().stream()
                .map(e -> {
                    double weight = totalValue.compareTo(BigDecimal.ZERO) == 0 ? 0.0
                            : e.getValue().divide(totalValue, 8, RoundingMode.HALF_UP).doubleValue();
                    return new SectorAllocation(e.getKey(), weight, e.getValue(), sectorSymbols.get(e.getKey()));
                })
                .sorted(Comparator.comparingDouble(SectorAllocation::weight).reversed())
                .toList();

        return new SectorExposureResponse(accountId, allocations);
    }
}
```

- [ ] **Step 5: Run tests**

```bash
mvn -B test -pl . -Dtest=SectorExposureServiceTest
```
Expected: 4 tests pass

- [ ] **Step 6: Add endpoint to PortfolioController**

Add to `src/main/java/com/finrisk/controller/PortfolioController.java` — add `SectorExposureService` field/constructor param, and the endpoint. Full updated controller (replacing the one from Task 3):

```java
package com.finrisk.controller;

import com.finrisk.dto.response.BetaResponse;
import com.finrisk.dto.response.PortfolioResponse;
import com.finrisk.dto.response.ProfitLossResponse;
import com.finrisk.dto.response.RiskScoreResponse;
import com.finrisk.dto.response.SectorExposureResponse;
import com.finrisk.service.BetaService;
import com.finrisk.service.PortfolioService;
import com.finrisk.service.ProfitLossService;
import com.finrisk.service.RiskService;
import com.finrisk.service.SectorExposureService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/accounts/{accountId}")
public class PortfolioController {

    private final PortfolioService portfolioService;
    private final ProfitLossService profitLossService;
    private final RiskService riskService;
    private final BetaService betaService;
    private final SectorExposureService sectorExposureService;

    public PortfolioController(
            PortfolioService portfolioService,
            ProfitLossService profitLossService,
            RiskService riskService,
            BetaService betaService,
            SectorExposureService sectorExposureService) {
        this.portfolioService = portfolioService;
        this.profitLossService = profitLossService;
        this.riskService = riskService;
        this.betaService = betaService;
        this.sectorExposureService = sectorExposureService;
    }

    @GetMapping("/portfolio")
    public PortfolioResponse portfolio(@PathVariable long accountId) {
        return portfolioService.getPortfolio(accountId);
    }

    @GetMapping("/profit-loss")
    public ProfitLossResponse profitLoss(@PathVariable long accountId) {
        return profitLossService.getProfitLoss(accountId);
    }

    @GetMapping("/risk")
    public RiskScoreResponse risk(@PathVariable long accountId) {
        return riskService.computeRisk(accountId);
    }

    @GetMapping("/beta")
    public BetaResponse beta(@PathVariable long accountId) {
        return betaService.computeBeta(accountId);
    }

    @GetMapping("/sector-exposure")
    public SectorExposureResponse sectorExposure(@PathVariable long accountId) {
        return sectorExposureService.computeSectorExposure(accountId);
    }
}
```

- [ ] **Step 7: Full test run**

```bash
mvn -B test
```
Expected: BUILD SUCCESS

- [ ] **Step 8: Commit**

```bash
git add src/main/java/com/finrisk/dto/response/SectorAllocation.java \
        src/main/java/com/finrisk/dto/response/SectorExposureResponse.java \
        src/main/java/com/finrisk/service/SectorExposureService.java \
        src/main/java/com/finrisk/controller/PortfolioController.java \
        src/test/java/com/finrisk/service/SectorExposureServiceTest.java
git commit -m "feat: add sector exposure endpoint GET /api/v1/accounts/{id}/sector-exposure"
```

---

### Task 5: Diversification service and endpoint

**Files:**
- Create: `src/main/java/com/finrisk/dto/response/AssetTypeAllocation.java`
- Create: `src/main/java/com/finrisk/dto/response/DiversificationResponse.java`
- Create: `src/main/java/com/finrisk/service/DiversificationService.java`
- Modify: `src/main/java/com/finrisk/controller/PortfolioController.java`
- Create: `src/test/java/com/finrisk/service/DiversificationServiceTest.java`

**Interfaces:**
- Consumes:
  - `PortfolioDao.cashBalance(long)` → `Optional<BigDecimal>`
  - `PortfolioDao.holdings(long)` → `List<Holding>`
  - `SectorExposureService.computeSectorExposure(long)` → `SectorExposureResponse`
  - `AccountNotFoundException`
- Produces:
  - `DiversificationService.computeDiversification(long accountId)` → `DiversificationResponse`
  - `GET /api/v1/accounts/{accountId}/diversification` → JSON `DiversificationResponse`

**Logic:**
```
weight_i   = holding.currentValue() / totalHoldingsValue
HHI        = Σ weight_i²
score      = round((1 − HHI) × 100, 2)
sectorCount    = distinct sectors from SectorExposureService
assetTypeCount = distinct AssetType values among holdings
assetTypeBreakdown = per-AssetType { assetType.name(), weight, value }, sorted by weight desc
```

- [ ] **Step 1: Write failing tests**

Create `src/test/java/com/finrisk/service/DiversificationServiceTest.java`:

```java
package com.finrisk.service;

import com.finrisk.dao.PortfolioDao;
import com.finrisk.dto.response.AssetTypeAllocation;
import com.finrisk.dto.response.DiversificationResponse;
import com.finrisk.dto.response.Holding;
import com.finrisk.dto.response.SectorAllocation;
import com.finrisk.dto.response.SectorExposureResponse;
import com.finrisk.exception.AccountNotFoundException;
import com.finrisk.model.AssetType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.data.Offset.offset;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class DiversificationServiceTest {

    @Mock PortfolioDao portfolioDao;
    @Mock SectorExposureService sectorExposureService;

    DiversificationService service;

    @BeforeEach
    void setUp() {
        service = new DiversificationService(portfolioDao, sectorExposureService);
    }

    @Test
    void throwsWhenAccountNotFound() {
        when(portfolioDao.cashBalance(99L)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.computeDiversification(99L))
                .isInstanceOf(AccountNotFoundException.class);
    }

    @Test
    void scoreIsZeroWhenSingleHolding() {
        // Single holding: weight = 1.0, HHI = 1.0, score = 0
        Holding h = new Holding(1L, "AAPL", "Apple", AssetType.STOCK, 10,
                BigDecimal.valueOf(180), BigDecimal.valueOf(1800));
        when(portfolioDao.cashBalance(1L)).thenReturn(Optional.of(BigDecimal.ZERO));
        when(portfolioDao.holdings(1L)).thenReturn(List.of(h));
        when(sectorExposureService.computeSectorExposure(1L))
                .thenReturn(new SectorExposureResponse(1L, List.of(
                        new SectorAllocation("Technology", 1.0, BigDecimal.valueOf(1800), List.of("AAPL")))));

        DiversificationResponse response = service.computeDiversification(1L);

        assertThat(response.score()).isCloseTo(0.0, offset(0.01));
        assertThat(response.hhiIndex()).isCloseTo(1.0, offset(0.01));
        assertThat(response.holdingCount()).isEqualTo(1);
        assertThat(response.sectorCount()).isEqualTo(1);
        assertThat(response.assetTypeCount()).isEqualTo(1);
    }

    @Test
    void scoreIsHigherWithEquallyWeightedHoldings() {
        // 4 equal holdings: each weight = 0.25, HHI = 4 × 0.0625 = 0.25, score = 75
        BigDecimal val = BigDecimal.valueOf(1000);
        List<Holding> holdings = List.of(
                new Holding(1L, "A", "A", AssetType.STOCK, 1, val, val),
                new Holding(2L, "B", "B", AssetType.STOCK, 1, val, val),
                new Holding(3L, "C", "C", AssetType.ETF, 1, val, val),
                new Holding(4L, "D", "D", AssetType.BOND, 1, val, val)
        );
        when(portfolioDao.cashBalance(1L)).thenReturn(Optional.of(BigDecimal.ZERO));
        when(portfolioDao.holdings(1L)).thenReturn(holdings);
        when(sectorExposureService.computeSectorExposure(1L))
                .thenReturn(new SectorExposureResponse(1L, List.of(
                        new SectorAllocation("Technology", 0.5, BigDecimal.valueOf(2000), List.of("A", "B")),
                        new SectorAllocation("Bonds", 0.25, BigDecimal.valueOf(1000), List.of("C")),
                        new SectorAllocation("Other", 0.25, BigDecimal.valueOf(1000), List.of("D")))));

        DiversificationResponse response = service.computeDiversification(1L);

        assertThat(response.score()).isCloseTo(75.0, offset(0.01));
        assertThat(response.hhiIndex()).isCloseTo(0.25, offset(0.01));
        assertThat(response.holdingCount()).isEqualTo(4);
        assertThat(response.sectorCount()).isEqualTo(3);
        assertThat(response.assetTypeCount()).isEqualTo(3); // STOCK, ETF, BOND
    }

    @Test
    void assetTypeBreakdownSortedByWeightDesc() {
        BigDecimal bigVal = BigDecimal.valueOf(3000);
        BigDecimal smallVal = BigDecimal.valueOf(1000);
        List<Holding> holdings = List.of(
                new Holding(1L, "A", "A", AssetType.STOCK, 1, bigVal, bigVal),
                new Holding(2L, "B", "B", AssetType.BOND, 1, smallVal, smallVal)
        );
        when(portfolioDao.cashBalance(1L)).thenReturn(Optional.of(BigDecimal.ZERO));
        when(portfolioDao.holdings(1L)).thenReturn(holdings);
        when(sectorExposureService.computeSectorExposure(1L))
                .thenReturn(new SectorExposureResponse(1L, List.of()));

        DiversificationResponse response = service.computeDiversification(1L);

        List<AssetTypeAllocation> breakdown = response.assetTypeBreakdown();
        assertThat(breakdown.get(0).assetType()).isEqualTo("STOCK");
        assertThat(breakdown.get(0).weight()).isCloseTo(0.75, offset(0.01));
        assertThat(breakdown.get(1).assetType()).isEqualTo("BOND");
        assertThat(breakdown.get(1).weight()).isCloseTo(0.25, offset(0.01));
    }
}
```

- [ ] **Step 2: Run to verify they fail**

```bash
mvn -B test -pl . -Dtest=DiversificationServiceTest
```
Expected: COMPILATION ERROR

- [ ] **Step 3: Create DTOs**

Create `src/main/java/com/finrisk/dto/response/AssetTypeAllocation.java`:
```java
package com.finrisk.dto.response;

import java.math.BigDecimal;

public record AssetTypeAllocation(String assetType, double weight, BigDecimal value) {}
```

Create `src/main/java/com/finrisk/dto/response/DiversificationResponse.java`:
```java
package com.finrisk.dto.response;

import java.util.List;

public record DiversificationResponse(
        long accountId,
        double score,
        double hhiIndex,
        int holdingCount,
        int sectorCount,
        int assetTypeCount,
        List<AssetTypeAllocation> assetTypeBreakdown) {}
```

- [ ] **Step 4: Create DiversificationService**

Create `src/main/java/com/finrisk/service/DiversificationService.java`:
```java
package com.finrisk.service;

import com.finrisk.dao.PortfolioDao;
import com.finrisk.dto.response.AssetTypeAllocation;
import com.finrisk.dto.response.DiversificationResponse;
import com.finrisk.dto.response.Holding;
import com.finrisk.dto.response.SectorExposureResponse;
import com.finrisk.exception.AccountNotFoundException;
import com.finrisk.model.AssetType;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

@Service
public class DiversificationService {

    private final PortfolioDao portfolioDao;
    private final SectorExposureService sectorExposureService;

    public DiversificationService(PortfolioDao portfolioDao, SectorExposureService sectorExposureService) {
        this.portfolioDao = portfolioDao;
        this.sectorExposureService = sectorExposureService;
    }

    public DiversificationResponse computeDiversification(long accountId) {
        if (portfolioDao.cashBalance(accountId).isEmpty()) {
            throw new AccountNotFoundException("Account not found");
        }

        List<Holding> holdings = portfolioDao.holdings(accountId);

        if (holdings.isEmpty()) {
            return new DiversificationResponse(accountId, 0.0, 1.0, 0, 0, 0, List.of());
        }

        BigDecimal totalValue = holdings.stream()
                .map(Holding::currentValue)
                .reduce(BigDecimal.ZERO, BigDecimal::add);

        // HHI = Σ weight_i²
        double hhi = 0.0;
        if (totalValue.compareTo(BigDecimal.ZERO) > 0) {
            for (Holding h : holdings) {
                double w = h.currentValue().divide(totalValue, 8, RoundingMode.HALF_UP).doubleValue();
                hhi += w * w;
            }
        } else {
            hhi = 1.0;
        }

        double score = BigDecimal.valueOf((1.0 - hhi) * 100.0)
                .setScale(2, RoundingMode.HALF_UP).doubleValue();

        // Asset type breakdown
        Map<AssetType, BigDecimal> typeValue = new LinkedHashMap<>();
        for (Holding h : holdings) {
            typeValue.merge(h.assetType(), h.currentValue(), BigDecimal::add);
        }

        List<AssetTypeAllocation> breakdown = typeValue.entrySet().stream()
                .map(e -> {
                    double w = totalValue.compareTo(BigDecimal.ZERO) == 0 ? 0.0
                            : e.getValue().divide(totalValue, 8, RoundingMode.HALF_UP).doubleValue();
                    return new AssetTypeAllocation(e.getKey().name(), w, e.getValue());
                })
                .sorted(Comparator.comparingDouble(AssetTypeAllocation::weight).reversed())
                .toList();

        SectorExposureResponse sectorExposure = sectorExposureService.computeSectorExposure(accountId);
        int sectorCount = sectorExposure.sectors().size();

        return new DiversificationResponse(
                accountId,
                score,
                BigDecimal.valueOf(hhi).setScale(6, RoundingMode.HALF_UP).doubleValue(),
                holdings.size(),
                sectorCount,
                breakdown.size(),
                breakdown);
    }
}
```

- [ ] **Step 5: Run tests**

```bash
mvn -B test -pl . -Dtest=DiversificationServiceTest
```
Expected: 4 tests pass

- [ ] **Step 6: Add endpoint to PortfolioController**

Full updated `src/main/java/com/finrisk/controller/PortfolioController.java`:

```java
package com.finrisk.controller;

import com.finrisk.dto.response.BetaResponse;
import com.finrisk.dto.response.DiversificationResponse;
import com.finrisk.dto.response.PortfolioResponse;
import com.finrisk.dto.response.ProfitLossResponse;
import com.finrisk.dto.response.RiskScoreResponse;
import com.finrisk.dto.response.SectorExposureResponse;
import com.finrisk.service.BetaService;
import com.finrisk.service.DiversificationService;
import com.finrisk.service.PortfolioService;
import com.finrisk.service.ProfitLossService;
import com.finrisk.service.RiskService;
import com.finrisk.service.SectorExposureService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/accounts/{accountId}")
public class PortfolioController {

    private final PortfolioService portfolioService;
    private final ProfitLossService profitLossService;
    private final RiskService riskService;
    private final BetaService betaService;
    private final SectorExposureService sectorExposureService;
    private final DiversificationService diversificationService;

    public PortfolioController(
            PortfolioService portfolioService,
            ProfitLossService profitLossService,
            RiskService riskService,
            BetaService betaService,
            SectorExposureService sectorExposureService,
            DiversificationService diversificationService) {
        this.portfolioService = portfolioService;
        this.profitLossService = profitLossService;
        this.riskService = riskService;
        this.betaService = betaService;
        this.sectorExposureService = sectorExposureService;
        this.diversificationService = diversificationService;
    }

    @GetMapping("/portfolio")
    public PortfolioResponse portfolio(@PathVariable long accountId) {
        return portfolioService.getPortfolio(accountId);
    }

    @GetMapping("/profit-loss")
    public ProfitLossResponse profitLoss(@PathVariable long accountId) {
        return profitLossService.getProfitLoss(accountId);
    }

    @GetMapping("/risk")
    public RiskScoreResponse risk(@PathVariable long accountId) {
        return riskService.computeRisk(accountId);
    }

    @GetMapping("/beta")
    public BetaResponse beta(@PathVariable long accountId) {
        return betaService.computeBeta(accountId);
    }

    @GetMapping("/sector-exposure")
    public SectorExposureResponse sectorExposure(@PathVariable long accountId) {
        return sectorExposureService.computeSectorExposure(accountId);
    }

    @GetMapping("/diversification")
    public DiversificationResponse diversification(@PathVariable long accountId) {
        return diversificationService.computeDiversification(accountId);
    }
}
```

- [ ] **Step 7: Full test run**

```bash
mvn -B test
```
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 8: Commit**

```bash
git add src/main/java/com/finrisk/dto/response/AssetTypeAllocation.java \
        src/main/java/com/finrisk/dto/response/DiversificationResponse.java \
        src/main/java/com/finrisk/service/DiversificationService.java \
        src/main/java/com/finrisk/controller/PortfolioController.java \
        src/test/java/com/finrisk/service/DiversificationServiceTest.java
git commit -m "feat: add diversification score endpoint GET /api/v1/accounts/{id}/diversification"
```
