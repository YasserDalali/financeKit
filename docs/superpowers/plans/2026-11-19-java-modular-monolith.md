# Java Modular Monolith Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Node valuation service, the Java risk service and the planned `data-ms` with one Java 21 Spring Boot monolith (`backend/`) built from DDD bounded contexts, deployed on Render next to the untouched Python `hybrid-rag` service.

**Architecture:** Four bounded contexts in one Maven multi-module build: **Data** (`marketdata-api` port + `marketdata` adapters), **Valuation**, **Portfolio + Risk** (`risk`), and an `app` module that wires them. Valuation and Risk depend only on the `MarketData` interface from `marketdata-api`; they cannot see FMP or Yahoo at compile time. The Data module maps each vendor's response format into domain types through one adapter per source, tries sources in order (FMP, then Yahoo), and caches results in process. PostgreSQL replaces SQL Server; the stored procedures become domain logic in Java, and the schema is applied by Flyway.

**Tech Stack:** Java 21, Spring Boot 3.3.6, Maven multi-module, plain JDBC (kept from the current code), PostgreSQL 16 + Flyway, Caffeine, Jackson, JUnit 5 + Mockito + AssertJ, Testcontainers, ArchUnit, Docker, Render Blueprint (`render.yaml`).

## Global Constraints

- Java 21; Spring Boot parent `3.3.6`; group id `com.finrisk`; version `0.1.0-SNAPSHOT`; all modules live under `backend/`.
- `risk` and `valuation` depend on `marketdata-api` only, never on `marketdata`. `app` is the only module that depends on everything. (Enforced by Maven and by the ArchUnit tests in Task 11.)
- `MarketData` keeps today's contract for the three existing methods: they never throw; they return an empty list or `CompanyProfile.unknown(symbol)` when nothing is available. New methods return `Optional` or an empty list.
- A market data source throws `SourceUnavailableException` for transport errors, HTTP 401/403/429/5xx and vendor "limit reached" bodies. It returns empty for "symbol not found". Exception messages and logs must never contain URLs or API keys.
- No test may touch the network. HTTP is faked through `HttpFetcher`.
- Money and prices persist as `NUMERIC(19,4)`. Analytics maths stays `double`, as in the current code.
- Postgres schema changes only through Flyway files in `backend/risk/src/main/resources/db/migration`. No stored procedures. The only trigger is the generic audit trigger in `V4__audit.sql`.
- Existing risk endpoints keep their paths under `/api/v1`. Valuation endpoints live under `/api/v1/valuation`.
- The backend reads `PORT` (Render sets it) and defaults to 8080. `hybrid-rag` stays on 8000.
- Never commit secrets. `.env` files stay untracked; commit only `.env.example`.
- End every commit message with the trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Decisions to confirm before executing

These were chosen so the plan is complete. Each is cheap to change now and costly later.

1. **Render does not run docker-compose.** It deploys one Docker image per service from a `render.yaml` Blueprint. The "docker compose package" becomes two things built from the same Dockerfiles: a root `docker-compose.yml` for local runs, and `render.yaml` for Render (Tasks 12 and 13).
2. **PostgreSQL** (confirmed). Render offers it managed; it has no managed SQL Server.
3. **In-process Caffeine cache replaces Redis.** One less service to run on Render. The cache is per instance, so it resets on deploy and is not shared if you scale to two instances.
4. **Yahoo is an unofficial fallback.** The adapter calls Yahoo's public web endpoints the way `yfinance` does, including the cookie-and-crumb handshake. Yahoo does not clear its data for redistribution and can change or block these endpoints without notice. It is on by default as the fallback; set `YAHOO_ENABLED=false` to turn it off. Yahoo has no peer-group endpoint, so peer analysis needs FMP.
5. **FMP endpoints.** The base URL stays configurable (`FMP_BASE_URL`, default `https://financialmodelingprep.com/api/v3`, same as today). If your key only works on FMP's newer API, change the URL and the paths in `FmpSource` in one place; Yahoo covers you meanwhile.
6. **Behaviour fixes made on purpose while porting valuation.** Shares outstanding now come from the income statement (`weightedAverageShsOut`); the Node code used the cash-flow `commonStock` field, which is a dollar amount, not a share count. DCF rejects non-positive free cash flow with HTTP 422 instead of returning a negative value.
7. **Repository layout.** `risk-management-ms` and `sector-valuation-ms` are nested git repos tracked as gitlinks. The code is copied into `backend/` as plain files (their history stays in the old repos, which are left on disk). `hybrid-rag` is also a gitlink with no `.gitmodules`, so Render cannot clone it. Task 14 vendors its files into the main repo. This overrides the "do not convert them" note in `CLAUDE.md`, which Task 14 rewrites.
8. **Seed data shrinks.** The 152-line T-SQL seed (DBCC, `sys.all_columns`) is replaced by a small Postgres dev seed.
9. **Out of scope:** the five free sources chosen earlier (EDGAR, FRED, World Bank, GDELT, Comtrade) and the stress-testing and fundamentals features. They arrive later as more `MarketDataSource` adapters or new contexts. The earlier `data-ms` plan in `tasks/todo.md` is superseded by this one. `hybrid-rag` code is not changed except for being vendored.

## Target structure

```
backend/
  pom.xml                                    parent, module list, dependency management
  marketdata-api/                            DATA PORT (pure Java, no Spring)
    src/main/java/com/finrisk/marketdata/
      MarketData.java  PricePoint.java  CompanyProfile.java  EtfHolding.java
      Quote.java  Fundamentals.java  ValuationMetric.java  Peer.java  SymbolPolicy.java
  marketdata/                                DATA ADAPTERS (Spring)
    src/main/java/com/finrisk/marketdata/
      source/   MarketDataSource.java  SourceUnavailableException.java
                HttpFetcher.java  JdkHttpFetcher.java
      fmp/      FmpSource.java  FmpMapper.java
      yahoo/    YahooSource.java  YahooMapper.java
      FailoverMarketData.java  CachingMarketData.java
      MarketDataConfiguration.java  MarketDataProperties.java
  valuation/                                 VALUATION CONTEXT
    src/main/java/com/finrisk/valuation/
      domain/       GrowthStage DcfInput DcfResult DcfModel DdmInput DdmResult DdmModel
                    LynchInput LynchResult LynchModel PeerStats ValuationSignal Verdict
                    InsufficientPeerDataException
      application/  ValuationService + command/outcome records + exceptions
      web/          ValuationController, request records, ValuationExceptionHandler
  risk/                                      PORTFOLIO + RISK CONTEXTS
    src/main/java/com/finrisk/
      shared/       Page ErrorBody Db SqlSort DatabaseConnection DaoException
      portfolio/    domain (model, exception, repository ports, factory, Holding)
                    application (account, asset, transaction, user, portfolio, P&L services, mapper)
                    infrastructure (Postgres JDBC repositories)
                    web (controllers, DTOs, exception handler)
      risk/         domain (strategy, ReturnsMath)
                    application (Risk, Beta, Alpha, Correlation, Drawdown, Downside,
                                 Diversification, SectorExposure, EtfLookThrough, PortfolioPrices)
                    web (RiskController, DTOs)
    src/main/resources/db/migration/V1__schema.sql V2__indexes.sql V3__views.sql V4__audit.sql
  app/                                       BOOT APP + WIRING + ARCHITECTURE TESTS
    src/main/java/com/finrisk/app/FinRiskApplication.java
    src/main/resources/application.yml
    Dockerfile
docker-compose.yml  .env.example  render.yaml        (repo root)
```

---

## Phase A: Data context

### Task 1: Maven skeleton and the Data port (`marketdata-api`)

**Files:**
- Create: `backend/pom.xml`
- Create: `backend/marketdata-api/pom.xml`
- Create: `backend/marketdata-api/src/main/java/com/finrisk/marketdata/{MarketData,PricePoint,CompanyProfile,EtfHolding,Quote,Fundamentals,ValuationMetric,Peer,SymbolPolicy}.java`
- Test: `backend/marketdata-api/src/test/java/com/finrisk/marketdata/{SymbolPolicyTest,ValuationMetricTest,CompanyProfileTest}.java`

**Interfaces:**
- Consumes: nothing.
- Produces (used by every later task):
  - `interface MarketData { List<PricePoint> fetchDailyPrices(String symbol, int days); CompanyProfile fetchProfile(String symbol); List<EtfHolding> fetchEtfHoldings(String etfSymbol); Optional<Quote> fetchQuote(String symbol); Optional<Fundamentals> fetchFundamentals(String symbol); Optional<BigDecimal> fetchMetric(String symbol, ValuationMetric metric); List<Peer> fetchPeers(String sector, int limit); }`
  - `record PricePoint(LocalDate date, BigDecimal close)`, `record CompanyProfile(String symbol, String sector, String industry, String companyName)` with `static CompanyProfile unknown(String symbol)`, `record EtfHolding(String symbol, String name, BigDecimal weight)` (weight is a fraction). These three keep the exact shape they have today, so existing risk code and tests keep compiling.
  - `record Quote(String symbol, BigDecimal price, BigDecimal sharesOutstanding, BigDecimal lastDividend)` (fields after `symbol` may be null), `record Fundamentals(BigDecimal freeCashFlow, BigDecimal sharesOutstanding, BigDecimal eps, BigDecimal epsGrowth)` (all nullable), `enum ValuationMetric { PE, PB, PS, EV_EBITDA; static ValuationMetric parse(String) }`, `record Peer(String symbol, String companyName)`.
  - `final class SymbolPolicy { static boolean isValid(String); static String normalize(String) }`

- [ ] **Step 1: Create the parent POM** (only the first module is listed; each later task adds its own `<module>`)

`backend/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.3.6</version>
    <relativePath/>
  </parent>

  <groupId>com.finrisk</groupId>
  <artifactId>finrisk-backend</artifactId>
  <version>0.1.0-SNAPSHOT</version>
  <packaging>pom</packaging>

  <properties>
    <java.version>21</java.version>
    <archunit.version>1.3.0</archunit.version>
    <testcontainers.version>1.20.4</testcontainers.version>
  </properties>

  <modules>
    <module>marketdata-api</module>
  </modules>

  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>com.finrisk</groupId><artifactId>marketdata-api</artifactId><version>${project.version}</version>
      </dependency>
      <dependency>
        <groupId>com.finrisk</groupId><artifactId>marketdata</artifactId><version>${project.version}</version>
      </dependency>
      <dependency>
        <groupId>com.finrisk</groupId><artifactId>valuation</artifactId><version>${project.version}</version>
      </dependency>
      <dependency>
        <groupId>com.finrisk</groupId><artifactId>risk</artifactId><version>${project.version}</version>
      </dependency>
      <dependency>
        <groupId>com.tngtech.archunit</groupId><artifactId>archunit-junit5</artifactId><version>${archunit.version}</version>
      </dependency>
      <dependency>
        <groupId>org.testcontainers</groupId><artifactId>testcontainers-bom</artifactId>
        <version>${testcontainers.version}</version><type>pom</type><scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
```

`backend/marketdata-api/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.finrisk</groupId>
    <artifactId>finrisk-backend</artifactId>
    <version>0.1.0-SNAPSHOT</version>
  </parent>
  <artifactId>marketdata-api</artifactId>
  <description>The Data port: what the rest of FinRisk may ask of market data. Pure Java, no Spring.</description>

  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 2: Write the failing tests**

`backend/marketdata-api/src/test/java/com/finrisk/marketdata/SymbolPolicyTest.java`:

```java
package com.finrisk.marketdata;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SymbolPolicyTest {

    @Test
    void acceptsTickersClassSharesCryptoIndexAndFxSymbols() {
        for (String ok : new String[] {"AAPL", "BRK.B", "BTC-USD", "^GSPC", "EURUSD=X", " msft "}) {
            assertThat(SymbolPolicy.isValid(ok)).as(ok).isTrue();
        }
    }

    @Test
    void rejectsNullBlankTooLongAndUnsafeSymbols() {
        for (String bad : new String[] {null, "", "   ", "A".repeat(16), "AAPL/../x", "A B", "AAPL?x=1", "AA&PL"}) {
            assertThat(SymbolPolicy.isValid(bad)).as(String.valueOf(bad)).isFalse();
        }
    }

    @Test
    void normalizeTrimsAndUppercases() {
        assertThat(SymbolPolicy.normalize("  aapl ")).isEqualTo("AAPL");
    }
}
```

`backend/marketdata-api/src/test/java/com/finrisk/marketdata/ValuationMetricTest.java`:

```java
package com.finrisk.marketdata;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ValuationMetricTest {

    @Test
    void parseIsCaseInsensitiveAndTrims() {
        assertThat(ValuationMetric.parse("ev_ebitda")).isEqualTo(ValuationMetric.EV_EBITDA);
        assertThat(ValuationMetric.parse(" pe ")).isEqualTo(ValuationMetric.PE);
    }

    @Test
    void parseRejectsUnknownValuesAndListsTheValidOnes() {
        assertThatThrownBy(() -> ValuationMetric.parse("roe"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("roe")
                .hasMessageContaining("EV_EBITDA");
        assertThatThrownBy(() -> ValuationMetric.parse(null)).isInstanceOf(IllegalArgumentException.class);
    }
}
```

`backend/marketdata-api/src/test/java/com/finrisk/marketdata/CompanyProfileTest.java`:

```java
package com.finrisk.marketdata;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class CompanyProfileTest {

    @Test
    void unknownProfileUsesTheSymbolAsNameAndUnknownSectorAndIndustry() {
        CompanyProfile p = CompanyProfile.unknown("ZZZ");
        assertThat(p).isEqualTo(new CompanyProfile("ZZZ", "Unknown", "Unknown", "ZZZ"));
    }
}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && mvn -B -pl marketdata-api test`
Expected: FAIL, compilation error "cannot find symbol: class SymbolPolicy" (and the other types).

- [ ] **Step 4: Write the implementation**

`backend/marketdata-api/src/main/java/com/finrisk/marketdata/PricePoint.java`:

```java
package com.finrisk.marketdata;

import java.math.BigDecimal;
import java.time.LocalDate;

public record PricePoint(LocalDate date, BigDecimal close) {}
```

`.../CompanyProfile.java`:

```java
package com.finrisk.marketdata;

public record CompanyProfile(String symbol, String sector, String industry, String companyName) {

    /** What callers get when no source knows the symbol. */
    public static CompanyProfile unknown(String symbol) {
        return new CompanyProfile(symbol, "Unknown", "Unknown", symbol);
    }
}
```

`.../EtfHolding.java`:

```java
package com.finrisk.marketdata;

import java.math.BigDecimal;

/** One constituent of an ETF; {@code weight} is a fraction (0.071 = 7.1%). */
public record EtfHolding(String symbol, String name, BigDecimal weight) {}
```

`.../Quote.java`:

```java
package com.finrisk.marketdata;

import java.math.BigDecimal;

/** Price facts valuation needs. Everything except {@code symbol} may be null when the source lacks it. */
public record Quote(String symbol, BigDecimal price, BigDecimal sharesOutstanding, BigDecimal lastDividend) {}
```

`.../Fundamentals.java`:

```java
package com.finrisk.marketdata;

import java.math.BigDecimal;

/** Latest annual figures. {@code epsGrowth} is a decimal (0.11 = 11%). Every field may be null. */
public record Fundamentals(BigDecimal freeCashFlow, BigDecimal sharesOutstanding, BigDecimal eps, BigDecimal epsGrowth) {}
```

`.../ValuationMetric.java`:

```java
package com.finrisk.marketdata;

import java.util.Arrays;

public enum ValuationMetric {
    PE, PB, PS, EV_EBITDA;

    public static ValuationMetric parse(String raw) {
        if (raw != null) {
            for (ValuationMetric m : values()) {
                if (m.name().equalsIgnoreCase(raw.trim())) {
                    return m;
                }
            }
        }
        throw new IllegalArgumentException(
                "Unknown metric '" + raw + "'; expected one of " + Arrays.toString(values()));
    }
}
```

`.../Peer.java`:

```java
package com.finrisk.marketdata;

public record Peer(String symbol, String companyName) {}
```

`.../SymbolPolicy.java`:

```java
package com.finrisk.marketdata;

import java.util.Locale;
import java.util.regex.Pattern;

/** The one rule for what may be sent to a vendor as a symbol. Keeps junk and URL tricks out of requests. */
public final class SymbolPolicy {

    private static final Pattern VALID = Pattern.compile("^[A-Za-z0-9.\\-^=]{1,15}$");

    private SymbolPolicy() {}

    public static boolean isValid(String symbol) {
        return symbol != null && VALID.matcher(symbol.trim()).matches();
    }

    /** Call only after {@link #isValid}. */
    public static String normalize(String symbol) {
        return symbol.trim().toUpperCase(Locale.ROOT);
    }
}
```

`.../MarketData.java`:

```java
package com.finrisk.marketdata;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

/**
 * The Data port. Risk and Valuation depend on this and nothing else about market data.
 * No method throws: "nothing available" is an empty list, an empty Optional, or
 * {@link CompanyProfile#unknown(String)}.
 */
public interface MarketData {

    /** Daily closes, newest first. */
    List<PricePoint> fetchDailyPrices(String symbol, int days);

    CompanyProfile fetchProfile(String symbol);

    /** Constituents with weights as fractions. */
    List<EtfHolding> fetchEtfHoldings(String etfSymbol);

    Optional<Quote> fetchQuote(String symbol);

    Optional<Fundamentals> fetchFundamentals(String symbol);

    Optional<BigDecimal> fetchMetric(String symbol, ValuationMetric metric);

    List<Peer> fetchPeers(String sector, int limit);
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && mvn -B -pl marketdata-api test`
Expected: `Tests run: 6, Failures: 0, Errors: 0` and `BUILD SUCCESS`.

- [ ] **Step 6: Commit**

```bash
git add backend/pom.xml backend/marketdata-api
git commit -m "feat(backend): maven skeleton and MarketData port"
```

---

### Task 2: FMP source and the HTTP seam

**Files:**
- Modify: `backend/pom.xml` (add `<module>marketdata</module>` after `marketdata-api`)
- Create: `backend/marketdata/pom.xml`
- Create: `backend/marketdata/src/main/java/com/finrisk/marketdata/source/{HttpFetcher,JdkHttpFetcher,SourceUnavailableException,MarketDataSource}.java`
- Create: `backend/marketdata/src/main/java/com/finrisk/marketdata/fmp/{FmpMapper,FmpSource}.java`
- Test: `backend/marketdata/src/test/java/com/finrisk/marketdata/support/FakeHttpFetcher.java`
- Test: `backend/marketdata/src/test/java/com/finrisk/marketdata/fmp/FmpSourceTest.java`

**Interfaces:**
- Consumes: everything from Task 1.
- Produces:
  - `interface HttpFetcher { HttpResult get(String url, Map<String,String> headers) throws IOException, InterruptedException; record HttpResult(int status, String body) {} }`
  - `final class JdkHttpFetcher implements HttpFetcher` (no-arg constructor; owns a cookie jar)
  - `class SourceUnavailableException extends RuntimeException` with constructor `(String message)`
  - `interface MarketDataSource { String name(); boolean available(); default List<PricePoint> dailyPrices(String symbol, int days); default Optional<CompanyProfile> profile(String symbol); default Optional<Quote> quote(String symbol); default List<EtfHolding> etfHoldings(String etfSymbol); default Optional<Fundamentals> fundamentals(String symbol); default Optional<BigDecimal> metric(String symbol, ValuationMetric metric); default List<Peer> peers(String sector, int limit); }` (defaults return empty)
  - `FmpSource(String apiKey, String baseUrl, HttpFetcher http, Clock clock)`, `name()` is `"fmp"`, `available()` is true when the key is not blank.
  - Test helper `FakeHttpFetcher` with `on(String urlContains, int status, String body)`, `failOn(String urlContains, IOException e)`, public `List<String> requests`.

- [ ] **Step 1: Register the module and create its POM**

In `backend/pom.xml` replace the `<modules>` block with:

```xml
  <modules>
    <module>marketdata-api</module>
    <module>marketdata</module>
  </modules>
```

`backend/marketdata/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.finrisk</groupId>
    <artifactId>finrisk-backend</artifactId>
    <version>0.1.0-SNAPSHOT</version>
  </parent>
  <artifactId>marketdata</artifactId>
  <description>Data adapters: one per vendor, plus failover and caching behind the MarketData port.</description>

  <dependencies>
    <dependency>
      <groupId>com.finrisk</groupId>
      <artifactId>marketdata-api</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter</artifactId>
    </dependency>
    <dependency>
      <groupId>com.fasterxml.jackson.core</groupId>
      <artifactId>jackson-databind</artifactId>
    </dependency>
    <dependency>
      <groupId>com.github.ben-manes.caffeine</groupId>
      <artifactId>caffeine</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 2: Create the infrastructure types** (interfaces and a thin JDK client; nothing to test on their own)

`backend/marketdata/src/main/java/com/finrisk/marketdata/source/HttpFetcher.java`:

```java
package com.finrisk.marketdata.source;

import java.io.IOException;
import java.util.Map;

/** The only way adapters touch the network. Tests replace it with a fake. */
public interface HttpFetcher {

    HttpResult get(String url, Map<String, String> headers) throws IOException, InterruptedException;

    record HttpResult(int status, String body) {}
}
```

`.../source/JdkHttpFetcher.java`:

```java
package com.finrisk.marketdata.source;

import java.io.IOException;
import java.net.CookieManager;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;

/** JDK HttpClient with timeouts and its own cookie jar (Yahoo needs a session cookie). One instance per source. */
public final class JdkHttpFetcher implements HttpFetcher {

    private final HttpClient client;
    private final Duration requestTimeout;

    public JdkHttpFetcher() {
        this(Duration.ofSeconds(5), Duration.ofSeconds(10));
    }

    public JdkHttpFetcher(Duration connectTimeout, Duration requestTimeout) {
        this.client = HttpClient.newBuilder()
                .connectTimeout(connectTimeout)
                .cookieHandler(new CookieManager())
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
        this.requestTimeout = requestTimeout;
    }

    @Override
    public HttpResult get(String url, Map<String, String> headers) throws IOException, InterruptedException {
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(url)).timeout(requestTimeout).GET();
        headers.forEach(request::header);
        HttpResponse<String> response = client.send(request.build(), HttpResponse.BodyHandlers.ofString());
        return new HttpResult(response.statusCode(), response.body());
    }
}
```

`.../source/SourceUnavailableException.java`:

```java
package com.finrisk.marketdata.source;

/** A source could not answer (network, rate limit, bad key, vendor error). Message must be free of URLs and keys. */
public class SourceUnavailableException extends RuntimeException {

    public SourceUnavailableException(String message) {
        super(message);
    }
}
```

`.../source/MarketDataSource.java`:

```java
package com.finrisk.marketdata.source;

import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.EtfHolding;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.Peer;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

/**
 * One vendor. Empty result = "this source has no data for that" (unknown symbol, unsupported capability).
 * {@link SourceUnavailableException} = "this source is broken right now"; the failover tries the next source.
 */
public interface MarketDataSource {

    String name();

    /** False when the source is not configured (for example, no API key). Unavailable sources are skipped. */
    boolean available();

    default List<PricePoint> dailyPrices(String symbol, int days) { return List.of(); }

    default Optional<CompanyProfile> profile(String symbol) { return Optional.empty(); }

    default Optional<Quote> quote(String symbol) { return Optional.empty(); }

    default List<EtfHolding> etfHoldings(String etfSymbol) { return List.of(); }

    default Optional<Fundamentals> fundamentals(String symbol) { return Optional.empty(); }

    default Optional<BigDecimal> metric(String symbol, ValuationMetric metric) { return Optional.empty(); }

    default List<Peer> peers(String sector, int limit) { return List.of(); }
}
```

- [ ] **Step 3: Write the test helper and the failing FMP tests**

`backend/marketdata/src/test/java/com/finrisk/marketdata/support/FakeHttpFetcher.java`:

```java
package com.finrisk.marketdata.support;

import com.finrisk.marketdata.source.HttpFetcher;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Scripted HTTP. A route matches when the URL contains its text. Several routes with the same text answer in order. */
public final class FakeHttpFetcher implements HttpFetcher {

    private record Route(String contains, int status, String body, IOException error) {}

    private final List<Route> routes = new ArrayList<>();
    private final List<Route> used = new ArrayList<>();
    public final List<String> requests = new ArrayList<>();

    public FakeHttpFetcher on(String urlContains, int status, String body) {
        routes.add(new Route(urlContains, status, body, null));
        return this;
    }

    public FakeHttpFetcher failOn(String urlContains, IOException error) {
        routes.add(new Route(urlContains, 0, null, error));
        return this;
    }

    @Override
    public HttpResult get(String url, Map<String, String> headers) throws IOException {
        requests.add(url);
        Route match = null;
        Route last = null;
        for (Route r : routes) {
            if (!url.contains(r.contains())) continue;
            last = r;
            if (!used.contains(r)) { match = r; break; }
        }
        if (match == null) match = last;
        if (match == null) throw new AssertionError("unscripted request: " + url);
        if (!used.contains(match)) used.add(match);
        if (match.error() != null) throw match.error();
        return new HttpResult(match.status(), match.body());
    }
}
```

`backend/marketdata/src/test/java/com/finrisk/marketdata/fmp/FmpSourceTest.java`:

```java
package com.finrisk.marketdata.fmp;

import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.EtfHolding;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.Peer;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;
import com.finrisk.marketdata.source.SourceUnavailableException;
import com.finrisk.marketdata.support.FakeHttpFetcher;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FmpSourceTest {

    private static final String KEY = "SECRETKEY";
    private static final Clock CLOCK = Clock.fixed(Instant.parse("2024-07-01T12:00:00Z"), ZoneOffset.UTC);

    private final FakeHttpFetcher http = new FakeHttpFetcher();
    private final FmpSource fmp = new FmpSource(KEY, "https://fmp.test/api/v3", http, CLOCK);

    @Test
    void dailyPricesAreParsedNewestFirstAndBadRowsSkipped() {
        http.on("/historical-price-full/AAPL", 200, """
                {"symbol":"AAPL","historical":[
                  {"date":"2024-06-28","close":182.5},
                  {"date":"2024-06-27","close":180.0},
                  {"date":"not-a-date","close":1}]}""");

        List<PricePoint> prices = fmp.dailyPrices("AAPL", 30);

        assertThat(prices).containsExactly(
                new PricePoint(LocalDate.of(2024, 6, 28), new BigDecimal("182.5")),
                new PricePoint(LocalDate.of(2024, 6, 27), new BigDecimal("180.0")));
        assertThat(http.requests.getFirst()).contains("from=2024-06-01").contains("apikey=" + KEY);
    }

    @Test
    void profileMapsSectorIndustryAndName() {
        http.on("/profile/AAPL", 200, """
                [{"symbol":"AAPL","companyName":"Apple Inc.","sector":"Technology","industry":"Consumer Electronics"}]""");

        assertThat(fmp.profile("AAPL"))
                .contains(new CompanyProfile("AAPL", "Technology", "Consumer Electronics", "Apple Inc."));
    }

    @Test
    void profileWithoutSectorIsEmpty() {
        http.on("/profile/SPY", 200, """
                [{"symbol":"SPY","companyName":"SPDR S&P 500","sector":""}]""");

        assertThat(fmp.profile("SPY")).isEmpty();
    }

    @Test
    void quoteDerivesSharesFromMarketCapAndPrice() {
        http.on("/profile/AAPL", 200, """
                [{"symbol":"AAPL","price":200,"mktCap":3000000,"lastDiv":0.96}]""");

        Quote q = fmp.quote("AAPL").orElseThrow();

        assertThat(q.price()).isEqualByComparingTo("200");
        assertThat(q.sharesOutstanding()).isEqualByComparingTo("15000");
        assertThat(q.lastDividend()).isEqualByComparingTo("0.96");
    }

    @Test
    void etfHoldingsConvertPercentToFractionAndSkipBadRows() {
        http.on("/etf-holder/SPY", 200, """
                [{"asset":"AAPL","name":"Apple","weightPercentage":7.1},
                 {"asset":"","name":"Nameless","weightPercentage":1},
                 {"asset":"MSFT","name":"Microsoft","weightPercentage":"oops"}]""");

        assertThat(fmp.etfHoldings("SPY"))
                .containsExactly(new EtfHolding("AAPL", "Apple", new BigDecimal("0.071")));
    }

    @Test
    void metricReadsTheTtmRatioAndIsEmptyWhenAbsent() {
        http.on("/ratios-ttm/AAPL", 200, """
                [{"priceEarningsRatioTTM":28.5,"priceToSalesRatioTTM":null}]""");

        assertThat(fmp.metric("AAPL", ValuationMetric.PE)).contains(new BigDecimal("28.5"));
        assertThat(fmp.metric("AAPL", ValuationMetric.PS)).isEmpty();
        assertThat(fmp.metric("AAPL", ValuationMetric.PB)).isEmpty();
    }

    @Test
    void fundamentalsMergeCashFlowIncomeAndGrowth() {
        http.on("/cash-flow-statement/AAPL", 200, "[{\"freeCashFlow\":99000000000}]")
            .on("/income-statement/AAPL", 200, "[{\"eps\":6.4,\"weightedAverageShsOut\":15000000000}]")
            .on("/financial-growth/AAPL", 200, "[{\"epsgrowth\":0.11}]");

        Fundamentals f = fmp.fundamentals("AAPL").orElseThrow();

        assertThat(f.freeCashFlow()).isEqualByComparingTo("99000000000");
        assertThat(f.sharesOutstanding()).isEqualByComparingTo("15000000000");
        assertThat(f.eps()).isEqualByComparingTo("6.4");
        assertThat(f.epsGrowth()).isEqualByComparingTo("0.11");
    }

    @Test
    void fundamentalsAreEmptyWhenNothingIsReported() {
        http.on("/cash-flow-statement/ZZZ", 200, "[]")
            .on("/income-statement/ZZZ", 200, "[]")
            .on("/financial-growth/ZZZ", 200, "[]");

        assertThat(fmp.fundamentals("ZZZ")).isEmpty();
    }

    @Test
    void peersComeFromTheScreenerForTheSector() {
        http.on("/stock-screener", 200, """
                [{"symbol":"MSFT","companyName":"Microsoft"},{"symbol":"","companyName":"x"},{"symbol":"ORCL","companyName":"Oracle"}]""");

        assertThat(fmp.peers("Technology", 50))
                .containsExactly(new Peer("MSFT", "Microsoft"), new Peer("ORCL", "Oracle"));
        assertThat(http.requests.getFirst()).contains("sector=Technology").contains("limit=50");
    }

    @Test
    void unknownSymbolIs404AndGivesEmpty() {
        http.on("/profile/NOPE", 404, "");

        assertThat(fmp.profile("NOPE")).isEqualTo(Optional.empty());
    }

    @Test
    void vendorLimitMessageInA200BodyIsTreatedAsUnavailableWithoutLeakingTheKey() {
        http.on("/profile/AAPL", 200, "{\"Error Message\":\"Limit Reach. Please upgrade your plan\"}");

        assertThatThrownBy(() -> fmp.profile("AAPL"))
                .isInstanceOf(SourceUnavailableException.class)
                .hasMessageNotContaining(KEY)
                .hasMessageNotContaining("http");
    }

    @Test
    void serverErrorsRateLimitsAndTransportFailuresAreUnavailable() {
        http.on("/profile/A", 500, "")
            .on("/profile/B", 429, "")
            .on("/profile/C", 401, "")
            .failOn("/profile/D", new IOException("connection reset"));

        for (String s : new String[] {"A", "B", "C", "D"}) {
            assertThatThrownBy(() -> fmp.profile(s))
                    .as(s)
                    .isInstanceOf(SourceUnavailableException.class)
                    .hasMessageNotContaining(KEY);
        }
    }

    @Test
    void aBlankKeyMeansNotAvailable() {
        assertThat(new FmpSource("", "https://fmp.test/api/v3", http, CLOCK).available()).isFalse();
        assertThat(fmp.available()).isTrue();
        assertThat(fmp.name()).isEqualTo("fmp");
    }
}
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd backend && mvn -B -pl marketdata -am test`
Expected: FAIL, compilation error "cannot find symbol: class FmpSource".

- [ ] **Step 5: Write the FMP mapper and source**

`backend/marketdata/src/main/java/com/finrisk/marketdata/fmp/FmpMapper.java`:

```java
package com.finrisk.marketdata.fmp;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.EtfHolding;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.Peer;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/** FMP's response format to FinRisk's domain types. Pure functions; every bad row is skipped, never thrown. */
final class FmpMapper {

    private static final ObjectMapper JSON = new ObjectMapper();

    JsonNode read(String body) throws JsonProcessingException {
        return JSON.readTree(body);
    }

    List<PricePoint> prices(JsonNode root) {
        List<PricePoint> out = new ArrayList<>();
        for (JsonNode n : root.path("historical")) {
            try {
                out.add(new PricePoint(LocalDate.parse(n.path("date").asText()), new BigDecimal(n.path("close").asText())));
            } catch (RuntimeException skip) {
                // bad row: skip only this row
            }
        }
        return out;
    }

    Optional<CompanyProfile> profile(String symbol, JsonNode root) {
        JsonNode p = first(root);
        String sector = text(p, "sector");
        if (p == null || sector.isEmpty()) return Optional.empty();
        String industry = text(p, "industry");
        String name = text(p, "companyName");
        return Optional.of(new CompanyProfile(
                symbol, sector, industry.isEmpty() ? "Unknown" : industry, name.isEmpty() ? symbol : name));
    }

    Optional<Quote> quote(String symbol, JsonNode root) {
        JsonNode p = first(root);
        BigDecimal price = decimal(p, "price");
        if (price == null) return Optional.empty();
        BigDecimal marketCap = decimal(p, "mktCap");
        BigDecimal shares = marketCap != null && price.signum() > 0
                ? marketCap.divide(price, 0, RoundingMode.HALF_UP) : null;
        return Optional.of(new Quote(symbol, price, shares, decimal(p, "lastDiv")));
    }

    /** FMP's weightPercentage is a percent (7.1 = 7.1%); domain weights are fractions. */
    List<EtfHolding> etfHoldings(JsonNode root) {
        List<EtfHolding> out = new ArrayList<>();
        if (!root.isArray()) return out;
        for (JsonNode n : root) {
            String asset = text(n, "asset");
            BigDecimal percent = decimal(n, "weightPercentage");
            if (asset.isEmpty() || percent == null) continue;
            String name = text(n, "name");
            out.add(new EtfHolding(asset, name.isEmpty() ? asset : name, percent.movePointLeft(2)));
        }
        return out;
    }

    Optional<BigDecimal> metric(JsonNode root, ValuationMetric metric) {
        String field = switch (metric) {
            case PE -> "priceEarningsRatioTTM";
            case PB -> "priceToBookRatioTTM";
            case PS -> "priceToSalesRatioTTM";
            case EV_EBITDA -> "enterpriseValueMultipleTTM";
        };
        return Optional.ofNullable(decimal(first(root), field));
    }

    List<Peer> peers(JsonNode root) {
        List<Peer> out = new ArrayList<>();
        if (!root.isArray()) return out;
        for (JsonNode n : root) {
            String symbol = text(n, "symbol");
            if (!symbol.isEmpty()) out.add(new Peer(symbol, text(n, "companyName")));
        }
        return out;
    }

    Optional<Fundamentals> fundamentals(JsonNode cashFlow, JsonNode income, JsonNode growth) {
        BigDecimal fcf = decimal(first(cashFlow), "freeCashFlow");
        BigDecimal shares = decimal(first(income), "weightedAverageShsOut");
        BigDecimal eps = decimal(first(income), "eps");
        BigDecimal epsGrowth = decimal(first(growth), "epsgrowth");
        if (fcf == null && shares == null && eps == null && epsGrowth == null) return Optional.empty();
        return Optional.of(new Fundamentals(fcf, shares, eps, epsGrowth));
    }

    private static JsonNode first(JsonNode root) {
        return root != null && root.isArray() && !root.isEmpty() ? root.get(0) : null;
    }

    private static String text(JsonNode node, String field) {
        if (node == null) return "";
        JsonNode v = node.path(field);
        return v.isMissingNode() || v.isNull() ? "" : v.asText("").trim();
    }

    private static BigDecimal decimal(JsonNode node, String field) {
        if (node == null) return null;
        JsonNode v = node.path(field);
        if (v.isMissingNode() || v.isNull() || v.asText().isBlank()) return null;
        try {
            return new BigDecimal(v.asText());
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
```

`backend/marketdata/src/main/java/com/finrisk/marketdata/fmp/FmpSource.java`:

```java
package com.finrisk.marketdata.fmp;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.MissingNode;
import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.EtfHolding;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.Peer;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;
import com.finrisk.marketdata.source.HttpFetcher;
import com.finrisk.marketdata.source.HttpFetcher.HttpResult;
import com.finrisk.marketdata.source.MarketDataSource;
import com.finrisk.marketdata.source.SourceUnavailableException;

import java.io.IOException;
import java.math.BigDecimal;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** Financial Modeling Prep. Endpoints are the v3 paths used today; change them here if the vendor moves. */
public final class FmpSource implements MarketDataSource {

    private static final String NAME = "fmp";

    private final String apiKey;
    private final String baseUrl;
    private final HttpFetcher http;
    private final Clock clock;
    private final FmpMapper mapper = new FmpMapper();

    public FmpSource(String apiKey, String baseUrl, HttpFetcher http, Clock clock) {
        this.apiKey = apiKey == null ? "" : apiKey.trim();
        this.baseUrl = baseUrl;
        this.http = http;
        this.clock = clock;
    }

    @Override public String name() { return NAME; }

    @Override public boolean available() { return !apiKey.isBlank(); }

    @Override
    public List<PricePoint> dailyPrices(String symbol, int days) {
        String from = LocalDate.now(clock).minusDays(days).toString();
        return mapper.prices(json("/historical-price-full/" + enc(symbol), "from=" + from));
    }

    @Override
    public Optional<CompanyProfile> profile(String symbol) {
        return mapper.profile(symbol, json("/profile/" + enc(symbol), ""));
    }

    @Override
    public Optional<Quote> quote(String symbol) {
        return mapper.quote(symbol, json("/profile/" + enc(symbol), ""));
    }

    @Override
    public List<EtfHolding> etfHoldings(String etfSymbol) {
        return mapper.etfHoldings(json("/etf-holder/" + enc(etfSymbol), ""));
    }

    @Override
    public Optional<BigDecimal> metric(String symbol, ValuationMetric metric) {
        return mapper.metric(json("/ratios-ttm/" + enc(symbol), ""), metric);
    }

    @Override
    public List<Peer> peers(String sector, int limit) {
        return mapper.peers(json("/stock-screener",
                "sector=" + enc(sector) + "&exchange=NYSE,NASDAQ&country=US&limit=" + limit));
    }

    @Override
    public Optional<Fundamentals> fundamentals(String symbol) {
        JsonNode cashFlow = json("/cash-flow-statement/" + enc(symbol), "limit=1");
        JsonNode income = json("/income-statement/" + enc(symbol), "limit=1");
        JsonNode growth = json("/financial-growth/" + enc(symbol), "limit=1");
        return mapper.fundamentals(cashFlow, income, growth);
    }

    /** GET and parse. Missing node = unknown symbol. Throws when the source cannot be used. */
    private JsonNode json(String path, String query) {
        String url = baseUrl + path + "?" + (query.isEmpty() ? "" : query + "&") + "apikey=" + enc(apiKey);
        HttpResult result;
        try {
            result = http.get(url, Map.of());
        } catch (IOException e) {
            throw new SourceUnavailableException(NAME + " transport error: " + e.getClass().getSimpleName());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new SourceUnavailableException(NAME + " request interrupted");
        }
        int status = result.status();
        if (status == 404) return MissingNode.getInstance();
        if (status == 401 || status == 403 || status == 429 || status >= 500) {
            throw new SourceUnavailableException(NAME + " HTTP " + status);
        }
        if (status != 200) return MissingNode.getInstance();
        try {
            JsonNode node = mapper.read(result.body());
            if (node.has("Error Message")) {
                throw new SourceUnavailableException(NAME + " rejected the request");
            }
            return node;
        } catch (JsonProcessingException e) {
            throw new SourceUnavailableException(NAME + " returned invalid JSON");
        }
    }

    /** Path and query encoding: URLEncoder is form encoding, so '+' becomes %20. */
    private static String enc(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && mvn -B -pl marketdata -am test`
Expected: `Tests run: 14` in `FmpSourceTest` plus the 6 from Task 1 (the last `[INFO] Tests run:` line shows 14 for the `marketdata` module), `BUILD SUCCESS`.

- [ ] **Step 7: Commit**

```bash
git add backend/pom.xml backend/marketdata
git commit -m "feat(marketdata): FMP source, HTTP seam and source SPI"
```

---

### Task 3: Yahoo source (the fallback)

**Files:**
- Create: `backend/marketdata/src/main/java/com/finrisk/marketdata/yahoo/{YahooMapper,YahooSource}.java`
- Test: `backend/marketdata/src/test/java/com/finrisk/marketdata/yahoo/YahooSourceTest.java`

**Interfaces:**
- Consumes: `HttpFetcher`, `MarketDataSource`, `SourceUnavailableException`, `FakeHttpFetcher` (Task 2); domain records (Task 1).
- Produces: `YahooSource(HttpFetcher http, Clock clock)`; `name()` is `"yahoo"`; `available()` always true. Supports `dailyPrices`, `profile`, `quote`, `etfHoldings` (top ten only), `fundamentals`, `metric`. Does not support `peers` (inherits the empty default).

- [ ] **Step 1: Write the failing tests**

`backend/marketdata/src/test/java/com/finrisk/marketdata/yahoo/YahooSourceTest.java`:

```java
package com.finrisk.marketdata.yahoo;

import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.EtfHolding;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;
import com.finrisk.marketdata.source.SourceUnavailableException;
import com.finrisk.marketdata.support.FakeHttpFetcher;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class YahooSourceTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2024-07-01T12:00:00Z"), ZoneOffset.UTC);

    private static final String SUMMARY = """
            {"quoteSummary":{"result":[{
              "assetProfile":{"sector":"Technology","industry":"Consumer Electronics"},
              "price":{"longName":"Apple Inc.","regularMarketPrice":{"raw":200.0,"fmt":"200.00"}},
              "summaryDetail":{"dividendRate":{"raw":0.96},"trailingPE":{"raw":31.5},"priceToSalesTrailing12Months":{"raw":8.2}},
              "defaultKeyStatistics":{"sharesOutstanding":{"raw":15000000000},"trailingEps":{"raw":6.4},
                                      "priceToBook":{"raw":45.1},"enterpriseToEbitda":{"raw":22.0}},
              "financialData":{"freeCashflow":{"raw":99000000000},"earningsGrowth":{"raw":0.11}},
              "topHoldings":{"holdings":[
                {"symbol":"AAPL","holdingName":"Apple Inc.","holdingPercent":{"raw":0.071}},
                {"symbol":"MSFT","holdingName":"Microsoft","holdingPercent":{"raw":0.065}},
                {"symbol":"","holdingPercent":{"raw":0.01}}]}
            }],"error":null}}""";

    private final FakeHttpFetcher http = new FakeHttpFetcher()
            .on("fc.yahoo.com", 404, "")
            .on("/v1/test/getcrumb", 200, "CRUMB123")
            .on("/v10/finance/quoteSummary/AAPL", 200, SUMMARY);
    private final YahooSource yahoo = new YahooSource(http, CLOCK);

    @Test
    void dailyPricesAreNewestFirstAndSkipNullCloses() {
        // 1719581400 = 2024-06-28T13:30Z, 1719667800 = 2024-06-29T13:30Z, 1719754200 = 2024-06-30T13:30Z
        http.on("/v8/finance/chart/AAPL", 200, """
                {"chart":{"result":[{"meta":{"gmtoffset":-14400},
                  "timestamp":[1719581400,1719667800,1719754200],
                  "indicators":{"quote":[{"close":[180.0,null,182.5]}]}}]}}""");

        List<PricePoint> prices = yahoo.dailyPrices("AAPL", 30);

        assertThat(prices).containsExactly(
                new PricePoint(LocalDate.of(2024, 6, 30), new BigDecimal("182.5")),
                new PricePoint(LocalDate.of(2024, 6, 28), new BigDecimal("180.0")));
        assertThat(http.requests.getFirst())
                .contains("period2=1719835200")           // clock now
                .contains("period1=1717243200")           // now - 30 days
                .contains("interval=1d");
    }

    @Test
    void priceDatesUseTheExchangeOffset() {
        // 01:00Z on 06-28 is still 06-27 in New York (offset -4h)
        http.on("/v8/finance/chart/AAPL", 200, """
                {"chart":{"result":[{"meta":{"gmtoffset":-14400},"timestamp":[1719536400],
                  "indicators":{"quote":[{"close":[181.0]}]}}]}}""");

        assertThat(yahoo.dailyPrices("AAPL", 5))
                .containsExactly(new PricePoint(LocalDate.of(2024, 6, 27), new BigDecimal("181.0")));
    }

    @Test
    void profileQuoteFundamentalsAndMetricsComeFromQuoteSummary() {
        assertThat(yahoo.profile("AAPL"))
                .contains(new CompanyProfile("AAPL", "Technology", "Consumer Electronics", "Apple Inc."));

        Quote q = yahoo.quote("AAPL").orElseThrow();
        assertThat(q.price()).isEqualByComparingTo("200.0");
        assertThat(q.sharesOutstanding()).isEqualByComparingTo("15000000000");
        assertThat(q.lastDividend()).isEqualByComparingTo("0.96");

        Fundamentals f = yahoo.fundamentals("AAPL").orElseThrow();
        assertThat(f.freeCashFlow()).isEqualByComparingTo("99000000000");
        assertThat(f.sharesOutstanding()).isEqualByComparingTo("15000000000");
        assertThat(f.eps()).isEqualByComparingTo("6.4");
        assertThat(f.epsGrowth()).isEqualByComparingTo("0.11");

        assertThat(yahoo.metric("AAPL", ValuationMetric.PE).orElseThrow()).isEqualByComparingTo("31.5");
        assertThat(yahoo.metric("AAPL", ValuationMetric.PB).orElseThrow()).isEqualByComparingTo("45.1");
        assertThat(yahoo.metric("AAPL", ValuationMetric.PS).orElseThrow()).isEqualByComparingTo("8.2");
        assertThat(yahoo.metric("AAPL", ValuationMetric.EV_EBITDA).orElseThrow()).isEqualByComparingTo("22.0");
    }

    @Test
    void etfHoldingsAreTheTopHoldingsAsFractions() {
        List<EtfHolding> holdings = yahoo.etfHoldings("AAPL");

        assertThat(holdings).containsExactly(
                new EtfHolding("AAPL", "Apple Inc.", new BigDecimal("0.071")),
                new EtfHolding("MSFT", "Microsoft", new BigDecimal("0.065")));
    }

    @Test
    void profileWithoutSectorIsEmptyAndPeersAreUnsupported() {
        http.on("/v10/finance/quoteSummary/SPY", 200,
                "{\"quoteSummary\":{\"result\":[{\"price\":{\"longName\":\"SPDR\"}}]}}");

        assertThat(yahoo.profile("SPY")).isEmpty();
        assertThat(yahoo.peers("Technology", 50)).isEmpty();
    }

    @Test
    void sessionHandshakeFetchesCookieThenCrumbAndSendsTheCrumb() {
        yahoo.quote("AAPL");

        assertThat(http.requests).hasSize(3);
        assertThat(http.requests.get(0)).contains("fc.yahoo.com");
        assertThat(http.requests.get(1)).contains("/v1/test/getcrumb");
        assertThat(http.requests.get(2)).contains("crumb=CRUMB123").contains("modules=");
    }

    @Test
    void anExpiredCrumbIsRefreshedOnceAndTheCallRetried() {
        FakeHttpFetcher retry = new FakeHttpFetcher()
                .on("fc.yahoo.com", 404, "")
                .on("/v1/test/getcrumb", 200, "CRUMB1")
                .on("/v1/test/getcrumb", 200, "CRUMB2")
                .on("/v10/finance/quoteSummary/AAPL", 401, "")
                .on("/v10/finance/quoteSummary/AAPL", 200, SUMMARY);

        assertThat(new YahooSource(retry, CLOCK).quote("AAPL")).isPresent();
        assertThat(retry.requests.getLast()).contains("crumb=CRUMB2");
    }

    @Test
    void aBadCrumbResponseIsUnavailable() {
        FakeHttpFetcher bad = new FakeHttpFetcher()
                .on("fc.yahoo.com", 404, "")
                .on("/v1/test/getcrumb", 200, "<html>Too Many Requests</html>");

        assertThatThrownBy(() -> new YahooSource(bad, CLOCK).quote("AAPL"))
                .isInstanceOf(SourceUnavailableException.class);
    }

    @Test
    void rateLimitingIsUnavailableAndUnknownSymbolsAreEmpty() {
        http.on("/v8/finance/chart/LIM", 429, "")
            .on("/v8/finance/chart/NOPE", 404, "");

        assertThatThrownBy(() -> yahoo.dailyPrices("LIM", 5)).isInstanceOf(SourceUnavailableException.class);
        assertThat(yahoo.dailyPrices("NOPE", 5)).isEmpty();
    }

    @Test
    void isAlwaysAvailableAndNamedYahoo() {
        assertThat(yahoo.available()).isTrue();
        assertThat(yahoo.name()).isEqualTo("yahoo");
    }
}
```

Time check used in the first test: `2024-07-01T12:00:00Z` is epoch `1719835200`; minus 30 days (2,592,000 s) is `1717243200`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && mvn -B -pl marketdata -am test -Dtest=YahooSourceTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL, compilation error "cannot find symbol: class YahooSource".

- [ ] **Step 3: Write the Yahoo mapper and source**

`backend/marketdata/src/main/java/com/finrisk/marketdata/yahoo/YahooMapper.java`:

```java
package com.finrisk.marketdata.yahoo;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.EtfHolding;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/** Yahoo's response format to FinRisk's domain types. Yahoo wraps numbers as {"raw": 1.5, "fmt": "1.50"}. */
final class YahooMapper {

    private static final ObjectMapper JSON = new ObjectMapper();

    JsonNode read(String body) throws JsonProcessingException {
        return JSON.readTree(body);
    }

    /** Chart response to closes, newest first. Dates use the exchange's own offset. */
    List<PricePoint> prices(JsonNode root) {
        JsonNode result = root.path("chart").path("result").path(0);
        JsonNode timestamps = result.path("timestamp");
        JsonNode closes = result.path("indicators").path("quote").path(0).path("close");
        int offsetSeconds = result.path("meta").path("gmtoffset").asInt(0);
        List<PricePoint> out = new ArrayList<>();
        for (int i = timestamps.size() - 1; i >= 0; i--) {
            JsonNode close = closes.path(i);
            if (close.isMissingNode() || close.isNull()) continue;
            LocalDate date = Instant.ofEpochSecond(timestamps.get(i).asLong() + offsetSeconds)
                    .atZone(ZoneOffset.UTC).toLocalDate();
            out.add(new PricePoint(date, BigDecimal.valueOf(close.asDouble())));
        }
        return out;
    }

    /** The first quoteSummary result: the container of all modules. */
    JsonNode summary(JsonNode root) {
        return root.path("quoteSummary").path("result").path(0);
    }

    Optional<CompanyProfile> profile(String symbol, JsonNode r) {
        String sector = text(r.path("assetProfile").path("sector"));
        if (sector.isEmpty()) return Optional.empty();
        String industry = text(r.path("assetProfile").path("industry"));
        String name = text(r.path("price").path("longName"));
        if (name.isEmpty()) name = text(r.path("price").path("shortName"));
        return Optional.of(new CompanyProfile(
                symbol, sector, industry.isEmpty() ? "Unknown" : industry, name.isEmpty() ? symbol : name));
    }

    Optional<Quote> quote(String symbol, JsonNode r) {
        BigDecimal price = raw(r.path("price").path("regularMarketPrice"));
        if (price == null) return Optional.empty();
        return Optional.of(new Quote(
                symbol,
                price,
                raw(r.path("defaultKeyStatistics").path("sharesOutstanding")),
                raw(r.path("summaryDetail").path("dividendRate"))));
    }

    Optional<Fundamentals> fundamentals(JsonNode r) {
        BigDecimal fcf = raw(r.path("financialData").path("freeCashflow"));
        BigDecimal shares = raw(r.path("defaultKeyStatistics").path("sharesOutstanding"));
        BigDecimal eps = raw(r.path("defaultKeyStatistics").path("trailingEps"));
        BigDecimal growth = raw(r.path("financialData").path("earningsGrowth"));
        if (fcf == null && shares == null && eps == null && growth == null) return Optional.empty();
        return Optional.of(new Fundamentals(fcf, shares, eps, growth));
    }

    Optional<BigDecimal> metric(JsonNode r, ValuationMetric metric) {
        JsonNode node = switch (metric) {
            case PE -> r.path("summaryDetail").path("trailingPE");
            case PB -> r.path("defaultKeyStatistics").path("priceToBook");
            case PS -> r.path("summaryDetail").path("priceToSalesTrailing12Months");
            case EV_EBITDA -> r.path("defaultKeyStatistics").path("enterpriseToEbitda");
        };
        return Optional.ofNullable(raw(node));
    }

    /** Yahoo publishes only an ETF's top holdings (about ten). Weights are already fractions. */
    List<EtfHolding> etfHoldings(JsonNode r) {
        List<EtfHolding> out = new ArrayList<>();
        for (JsonNode h : r.path("topHoldings").path("holdings")) {
            String symbol = text(h.path("symbol"));
            BigDecimal weight = raw(h.path("holdingPercent"));
            if (symbol.isEmpty() || weight == null) continue;
            String name = text(h.path("holdingName"));
            out.add(new EtfHolding(symbol, name.isEmpty() ? symbol : name, weight));
        }
        return out;
    }

    private static String text(JsonNode n) {
        return n.isMissingNode() || n.isNull() ? "" : n.asText("").trim();
    }

    private static BigDecimal raw(JsonNode n) {
        JsonNode v = n.isObject() ? n.path("raw") : n;
        return v.isNumber() ? v.decimalValue() : null;
    }
}
```

`backend/marketdata/src/main/java/com/finrisk/marketdata/yahoo/YahooSource.java`:

```java
package com.finrisk.marketdata.yahoo;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.MissingNode;
import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.EtfHolding;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;
import com.finrisk.marketdata.source.HttpFetcher;
import com.finrisk.marketdata.source.HttpFetcher.HttpResult;
import com.finrisk.marketdata.source.MarketDataSource;
import com.finrisk.marketdata.source.SourceUnavailableException;

import java.io.IOException;
import java.math.BigDecimal;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Yahoo Finance through its public web endpoints, the way the yfinance library does it. Unofficial: Yahoo may
 * change or block these without notice, and its data is not cleared for redistribution. Fallback use only.
 * Prices need no login; the quoteSummary endpoint needs a session cookie plus a "crumb" token.
 */
public final class YahooSource implements MarketDataSource {

    private static final String NAME = "yahoo";
    private static final String COOKIE_URL = "https://fc.yahoo.com";
    private static final String CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb";
    private static final String CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/";
    private static final String SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/";
    private static final String MODULES =
            "assetProfile,price,summaryDetail,defaultKeyStatistics,financialData,topHoldings";
    private static final Map<String, String> HEADERS = Map.of(
            "User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept", "application/json");

    private final HttpFetcher http;
    private final Clock clock;
    private final YahooMapper mapper = new YahooMapper();
    private String crumb;

    public YahooSource(HttpFetcher http, Clock clock) {
        this.http = http;
        this.clock = clock;
    }

    @Override public String name() { return NAME; }

    @Override public boolean available() { return true; }

    @Override
    public List<PricePoint> dailyPrices(String symbol, int days) {
        long period2 = clock.instant().getEpochSecond();
        long period1 = period2 - days * 86_400L;
        String url = CHART_URL + enc(symbol) + "?period1=" + period1 + "&period2=" + period2 + "&interval=1d";
        return mapper.prices(body(fetch(url)));
    }

    @Override
    public Optional<CompanyProfile> profile(String symbol) {
        return mapper.profile(symbol, summary(symbol));
    }

    @Override
    public Optional<Quote> quote(String symbol) {
        return mapper.quote(symbol, summary(symbol));
    }

    @Override
    public Optional<Fundamentals> fundamentals(String symbol) {
        return mapper.fundamentals(summary(symbol));
    }

    @Override
    public Optional<BigDecimal> metric(String symbol, ValuationMetric metric) {
        return mapper.metric(summary(symbol), metric);
    }

    @Override
    public List<EtfHolding> etfHoldings(String etfSymbol) {
        return mapper.etfHoldings(summary(etfSymbol));
    }

    /** quoteSummary result for the symbol. A rejected crumb is refreshed once and the call retried. */
    private JsonNode summary(String symbol) {
        for (int attempt = 0; attempt < 2; attempt++) {
            HttpResult result = fetch(SUMMARY_URL + enc(symbol) + "?modules=" + MODULES + "&crumb=" + enc(crumb()));
            if (result.status() == 401 || result.status() == 403) {
                forgetCrumb();
                continue;
            }
            return mapper.summary(body(result));
        }
        throw new SourceUnavailableException(NAME + " rejected the session crumb");
    }

    private synchronized String crumb() {
        if (crumb == null) {
            fetch(COOKIE_URL); // sets the session cookie; its 404 body is irrelevant
            HttpResult result = fetch(CRUMB_URL);
            String value = result.body() == null ? "" : result.body().trim();
            if (result.status() != 200 || value.isEmpty() || value.contains("<") || value.length() > 64) {
                throw new SourceUnavailableException(NAME + " could not obtain a session crumb");
            }
            crumb = value;
        }
        return crumb;
    }

    private synchronized void forgetCrumb() {
        crumb = null;
    }

    private HttpResult fetch(String url) {
        try {
            return http.get(url, HEADERS);
        } catch (IOException e) {
            throw new SourceUnavailableException(NAME + " transport error: " + e.getClass().getSimpleName());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new SourceUnavailableException(NAME + " request interrupted");
        }
    }

    /** Parse a 200 body; 404 and other client errors are "no data"; throttling and server errors are unavailable. */
    private JsonNode body(HttpResult result) {
        int status = result.status();
        if (status == 429 || status >= 500) throw new SourceUnavailableException(NAME + " HTTP " + status);
        if (status != 200) return MissingNode.getInstance();
        try {
            return mapper.read(result.body());
        } catch (JsonProcessingException e) {
            throw new SourceUnavailableException(NAME + " returned invalid JSON");
        }
    }

    private static String enc(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && mvn -B -pl marketdata -am test`
Expected: `Tests run: 10` for `YahooSourceTest`, no failures, `BUILD SUCCESS`.

- [ ] **Step 5: Commit**

```bash
git add backend/marketdata
git commit -m "feat(marketdata): Yahoo fallback source with crumb session"
```

---

### Task 4: Failover, caching and Spring wiring

**Files:**
- Create: `backend/marketdata/src/main/java/com/finrisk/marketdata/{FailoverMarketData,CachingMarketData,MarketDataProperties,MarketDataConfiguration}.java`
- Test: `backend/marketdata/src/test/java/com/finrisk/marketdata/{FailoverMarketDataTest,CachingMarketDataTest,MarketDataConfigurationTest}.java`

**Interfaces:**
- Consumes: `MarketData`, `SymbolPolicy` (Task 1); `MarketDataSource`, `SourceUnavailableException`, `JdkHttpFetcher`, `FmpSource`, `YahooSource`, `FakeHttpFetcher` (Tasks 2-3).
- Produces:
  - `FailoverMarketData(List<MarketDataSource> sources) implements MarketData`
  - `CachingMarketData(MarketData delegate, CachingMarketData.Ttls ttls) implements MarketData`, with `record Ttls(Duration prices, Duration profile, Duration etf, Duration quote, Duration fundamentals, Duration ratios)` and `static Ttls defaults()`
  - `MarketDataProperties(List<String> sources, Fmp fmp, Yahoo yahoo)` bound to prefix `marketdata`
  - `MarketDataConfiguration` exposing a `MarketData` bean, plus package-private `static MarketData build(MarketDataProperties p, Supplier<HttpFetcher> fetchers, Clock clock)`

- [ ] **Step 1: Write the failing failover tests**

`backend/marketdata/src/test/java/com/finrisk/marketdata/FailoverMarketDataTest.java`:

```java
package com.finrisk.marketdata;

import com.finrisk.marketdata.source.MarketDataSource;
import com.finrisk.marketdata.source.SourceUnavailableException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class FailoverMarketDataTest {

    private static final List<PricePoint> FMP_PRICES =
            List.of(new PricePoint(LocalDate.of(2024, 6, 28), new BigDecimal("1")));
    private static final List<PricePoint> YAHOO_PRICES =
            List.of(new PricePoint(LocalDate.of(2024, 6, 28), new BigDecimal("2")));

    private final MarketDataSource fmp = mock(MarketDataSource.class);
    private final MarketDataSource yahoo = mock(MarketDataSource.class);
    private FailoverMarketData data;

    @BeforeEach
    void setUp() {
        when(fmp.name()).thenReturn("fmp");
        when(fmp.available()).thenReturn(true);
        when(yahoo.name()).thenReturn("yahoo");
        when(yahoo.available()).thenReturn(true);
        data = new FailoverMarketData(List.of(fmp, yahoo));
    }

    @Test
    void firstSourceWinsWhenItHasData() {
        when(fmp.dailyPrices("AAPL", 30)).thenReturn(FMP_PRICES);

        assertThat(data.fetchDailyPrices("AAPL", 30)).isEqualTo(FMP_PRICES);
        verify(yahoo, never()).dailyPrices(anyString(), anyInt());
    }

    @Test
    void fallsBackWhenThePrimaryIsUnavailable() {
        when(fmp.dailyPrices("AAPL", 30)).thenThrow(new SourceUnavailableException("fmp HTTP 429"));
        when(yahoo.dailyPrices("AAPL", 30)).thenReturn(YAHOO_PRICES);

        assertThat(data.fetchDailyPrices("AAPL", 30)).isEqualTo(YAHOO_PRICES);
    }

    @Test
    void fallsBackWhenThePrimaryHasNoData() {
        when(fmp.dailyPrices("AAPL", 30)).thenReturn(List.of());
        when(yahoo.dailyPrices("AAPL", 30)).thenReturn(YAHOO_PRICES);

        assertThat(data.fetchDailyPrices("AAPL", 30)).isEqualTo(YAHOO_PRICES);
    }

    @Test
    void anUnexpectedRuntimeFailureAlsoFallsBack() {
        when(fmp.dailyPrices("AAPL", 30)).thenThrow(new IllegalStateException("boom"));
        when(yahoo.dailyPrices("AAPL", 30)).thenReturn(YAHOO_PRICES);

        assertThat(data.fetchDailyPrices("AAPL", 30)).isEqualTo(YAHOO_PRICES);
    }

    @Test
    void skipsSourcesThatAreNotAvailable() {
        when(fmp.available()).thenReturn(false);
        when(yahoo.dailyPrices("AAPL", 30)).thenReturn(YAHOO_PRICES);

        assertThat(data.fetchDailyPrices("AAPL", 30)).isEqualTo(YAHOO_PRICES);
        verify(fmp, never()).dailyPrices(anyString(), anyInt());
    }

    @Test
    void safeDefaultsWhenEverySourceFails() {
        when(fmp.profile("ZZZ")).thenThrow(new SourceUnavailableException("down"));
        when(yahoo.profile("ZZZ")).thenThrow(new SourceUnavailableException("down"));

        assertThat(data.fetchProfile("ZZZ")).isEqualTo(CompanyProfile.unknown("ZZZ"));
        assertThat(data.fetchDailyPrices("ZZZ", 5)).isEmpty();
        assertThat(data.fetchEtfHoldings("ZZZ")).isEmpty();
        assertThat(data.fetchQuote("ZZZ")).isEqualTo(Optional.empty());
        assertThat(data.fetchFundamentals("ZZZ")).isEmpty();
        assertThat(data.fetchMetric("ZZZ", ValuationMetric.PE)).isEmpty();
        assertThat(data.fetchPeers("Technology", 5)).isEmpty();
    }

    @Test
    void invalidSymbolsNeverReachAnySource() {
        assertThat(data.fetchDailyPrices("AAPL/../x", 30)).isEmpty();
        assertThat(data.fetchProfile("A B")).isEqualTo(CompanyProfile.unknown("A B"));
        assertThat(data.fetchDailyPrices("AAPL", 0)).isEmpty();

        verifyNoInteractions(yahoo);
        verify(fmp, never()).dailyPrices(anyString(), anyInt());
    }

    @Test
    void symbolsAreNormalizedBeforeTheyReachASource() {
        when(fmp.dailyPrices("AAPL", 30)).thenReturn(FMP_PRICES);

        assertThat(data.fetchDailyPrices("  aapl ", 30)).isEqualTo(FMP_PRICES);
    }

    @Test
    void quoteAndPeersFailOverToo() {
        Quote quote = new Quote("AAPL", new BigDecimal("200"), null, null);
        when(fmp.quote("AAPL")).thenThrow(new SourceUnavailableException("down"));
        when(yahoo.quote("AAPL")).thenReturn(Optional.of(quote));
        when(fmp.peers("Technology", 5)).thenReturn(List.of(new Peer("MSFT", "Microsoft")));

        assertThat(data.fetchQuote("AAPL")).contains(quote);
        assertThat(data.fetchPeers("Technology", 5)).containsExactly(new Peer("MSFT", "Microsoft"));
    }
}
```

- [ ] **Step 2: Write the failing cache tests**

`backend/marketdata/src/test/java/com/finrisk/marketdata/CachingMarketDataTest.java`:

```java
package com.finrisk.marketdata;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class CachingMarketDataTest {

    private final MarketData delegate = mock(MarketData.class);
    private CachingMarketData cached;

    @BeforeEach
    void setUp() {
        cached = new CachingMarketData(delegate, CachingMarketData.Ttls.defaults());
    }

    @Test
    void repeatedPriceRequestsHitTheDelegateOnce() {
        List<PricePoint> prices = List.of(new PricePoint(LocalDate.of(2024, 6, 28), new BigDecimal("1")));
        when(delegate.fetchDailyPrices("AAPL", 30)).thenReturn(prices);

        assertThat(cached.fetchDailyPrices("AAPL", 30)).isEqualTo(prices);
        assertThat(cached.fetchDailyPrices("aapl ", 30)).isEqualTo(prices);

        verify(delegate, times(1)).fetchDailyPrices("AAPL", 30);
    }

    @Test
    void differentDayCountsAreDifferentEntries() {
        when(delegate.fetchDailyPrices("AAPL", 30)).thenReturn(List.of(new PricePoint(LocalDate.now(), BigDecimal.ONE)));
        when(delegate.fetchDailyPrices("AAPL", 90)).thenReturn(List.of(new PricePoint(LocalDate.now(), BigDecimal.TEN)));

        cached.fetchDailyPrices("AAPL", 30);
        cached.fetchDailyPrices("AAPL", 90);

        verify(delegate).fetchDailyPrices("AAPL", 30);
        verify(delegate).fetchDailyPrices("AAPL", 90);
    }

    @Test
    void emptyResultsAreNeverCached() {
        when(delegate.fetchDailyPrices("AAPL", 30)).thenReturn(List.of());
        when(delegate.fetchQuote("AAPL")).thenReturn(Optional.empty());
        when(delegate.fetchEtfHoldings("SPY")).thenReturn(List.of());

        cached.fetchDailyPrices("AAPL", 30);
        cached.fetchDailyPrices("AAPL", 30);
        cached.fetchQuote("AAPL");
        cached.fetchQuote("AAPL");
        cached.fetchEtfHoldings("SPY");
        cached.fetchEtfHoldings("SPY");

        verify(delegate, times(2)).fetchDailyPrices("AAPL", 30);
        verify(delegate, times(2)).fetchQuote("AAPL");
        verify(delegate, times(2)).fetchEtfHoldings("SPY");
    }

    @Test
    void unknownProfilesAreNotCachedButKnownOnesAre() {
        CompanyProfile known = new CompanyProfile("AAPL", "Technology", "Consumer Electronics", "Apple Inc.");
        when(delegate.fetchProfile("AAPL")).thenReturn(known);
        when(delegate.fetchProfile("ZZZ")).thenReturn(CompanyProfile.unknown("ZZZ"));

        cached.fetchProfile("AAPL");
        cached.fetchProfile("AAPL");
        cached.fetchProfile("ZZZ");
        cached.fetchProfile("ZZZ");

        verify(delegate, times(1)).fetchProfile("AAPL");
        verify(delegate, times(2)).fetchProfile("ZZZ");
    }

    @Test
    void metricsFundamentalsAndPeersAreCachedWhenPresent() {
        when(delegate.fetchMetric("AAPL", ValuationMetric.PE)).thenReturn(Optional.of(new BigDecimal("28.5")));
        when(delegate.fetchFundamentals("AAPL"))
                .thenReturn(Optional.of(new Fundamentals(BigDecimal.ONE, BigDecimal.TEN, null, null)));
        when(delegate.fetchPeers("Technology", 50)).thenReturn(List.of(new Peer("MSFT", "Microsoft")));

        for (int i = 0; i < 3; i++) {
            cached.fetchMetric("AAPL", ValuationMetric.PE);
            cached.fetchFundamentals("AAPL");
            cached.fetchPeers("Technology", 50);
        }

        verify(delegate, times(1)).fetchMetric("AAPL", ValuationMetric.PE);
        verify(delegate, times(1)).fetchFundamentals("AAPL");
        verify(delegate, times(1)).fetchPeers("Technology", 50);
    }
}
```

- [ ] **Step 3: Write the failing configuration tests**

`backend/marketdata/src/test/java/com/finrisk/marketdata/MarketDataConfigurationTest.java`:

```java
package com.finrisk.marketdata;

import com.finrisk.marketdata.MarketDataProperties.Fmp;
import com.finrisk.marketdata.MarketDataProperties.Yahoo;
import com.finrisk.marketdata.support.FakeHttpFetcher;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MarketDataConfigurationTest {

    private static final Clock CLOCK = Clock.fixed(Instant.parse("2024-07-01T12:00:00Z"), ZoneOffset.UTC);
    private static final String CHART = """
            {"chart":{"result":[{"meta":{"gmtoffset":0},"timestamp":[1719581400],
              "indicators":{"quote":[{"close":[182.5]}]}}]}}""";

    @Test
    void aBlankFmpKeySkipsFmpAndYahooAnswers() {
        FakeHttpFetcher http = new FakeHttpFetcher().on("/v8/finance/chart/AAPL", 200, CHART); // any FMP call would be unscripted
        MarketDataProperties props = new MarketDataProperties(
                List.of("fmp", "yahoo"), new Fmp("", "https://fmp.test/api/v3"), new Yahoo(true));

        MarketData data = MarketDataConfiguration.build(props, () -> http, CLOCK);

        assertThat(data.fetchDailyPrices("AAPL", 30)).hasSize(1);
        assertThat(http.requests).allMatch(url -> url.contains("yahoo.com"));
    }

    @Test
    void disablingYahooRemovesTheFallback() {
        FakeHttpFetcher http = new FakeHttpFetcher();
        MarketDataProperties props = new MarketDataProperties(
                List.of("fmp", "yahoo"), new Fmp("", "https://fmp.test/api/v3"), new Yahoo(false));

        MarketData data = MarketDataConfiguration.build(props, () -> http, CLOCK);

        assertThat(data.fetchDailyPrices("AAPL", 30)).isEmpty();
        assertThat(http.requests).isEmpty();
    }

    @Test
    void unknownSourceNamesFailFast() {
        MarketDataProperties props = new MarketDataProperties(
                List.of("bloomberg"), new Fmp("", "x"), new Yahoo(true));

        assertThatThrownBy(() -> MarketDataConfiguration.build(props, FakeHttpFetcher::new, CLOCK))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("bloomberg");
    }
}
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd backend && mvn -B -pl marketdata -am test`
Expected: FAIL, compilation errors "cannot find symbol: class FailoverMarketData / CachingMarketData / MarketDataProperties / MarketDataConfiguration".

- [ ] **Step 5: Write the implementations**

`backend/marketdata/src/main/java/com/finrisk/marketdata/FailoverMarketData.java`:

```java
package com.finrisk.marketdata;

import com.finrisk.marketdata.source.MarketDataSource;
import com.finrisk.marketdata.source.SourceUnavailableException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;
import java.util.function.Function;

/**
 * Asks each configured source in order and returns the first answer that has data. A source that is unavailable,
 * throws, or has nothing for the symbol is skipped. Keeps the port's "never throws" contract.
 */
public final class FailoverMarketData implements MarketData {

    private static final Logger log = LoggerFactory.getLogger(FailoverMarketData.class);

    private final List<MarketDataSource> sources;

    public FailoverMarketData(List<MarketDataSource> sources) {
        this.sources = List.copyOf(sources);
    }

    @Override
    public List<PricePoint> fetchDailyPrices(String symbol, int days) {
        if (!SymbolPolicy.isValid(symbol) || days < 1) return List.of();
        String s = SymbolPolicy.normalize(symbol);
        return firstList("dailyPrices", s, src -> src.dailyPrices(s, days));
    }

    @Override
    public CompanyProfile fetchProfile(String symbol) {
        if (!SymbolPolicy.isValid(symbol)) return CompanyProfile.unknown(symbol);
        String s = SymbolPolicy.normalize(symbol);
        return first("profile", s, src -> src.profile(s)).orElseGet(() -> CompanyProfile.unknown(s));
    }

    @Override
    public List<EtfHolding> fetchEtfHoldings(String etfSymbol) {
        if (!SymbolPolicy.isValid(etfSymbol)) return List.of();
        String s = SymbolPolicy.normalize(etfSymbol);
        return firstList("etfHoldings", s, src -> src.etfHoldings(s));
    }

    @Override
    public Optional<Quote> fetchQuote(String symbol) {
        if (!SymbolPolicy.isValid(symbol)) return Optional.empty();
        String s = SymbolPolicy.normalize(symbol);
        return first("quote", s, src -> src.quote(s));
    }

    @Override
    public Optional<Fundamentals> fetchFundamentals(String symbol) {
        if (!SymbolPolicy.isValid(symbol)) return Optional.empty();
        String s = SymbolPolicy.normalize(symbol);
        return first("fundamentals", s, src -> src.fundamentals(s));
    }

    @Override
    public Optional<BigDecimal> fetchMetric(String symbol, ValuationMetric metric) {
        if (!SymbolPolicy.isValid(symbol) || metric == null) return Optional.empty();
        String s = SymbolPolicy.normalize(symbol);
        return first("metric", s, src -> src.metric(s, metric));
    }

    @Override
    public List<Peer> fetchPeers(String sector, int limit) {
        if (sector == null || sector.isBlank() || limit < 1) return List.of();
        return firstList("peers", sector, src -> src.peers(sector, limit));
    }

    private <T> Optional<T> first(String op, String subject, Function<MarketDataSource, Optional<T>> call) {
        for (MarketDataSource source : sources) {
            if (!source.available()) continue;
            try {
                Optional<T> result = call.apply(source);
                if (result != null && result.isPresent()) return result;
            } catch (RuntimeException e) {
                // Source messages are written without URLs or keys, so SourceUnavailableException may be logged.
                String reason = e instanceof SourceUnavailableException ? e.getMessage() : e.getClass().getSimpleName();
                log.warn("market data source {} failed on {} {}: {}", source.name(), op, subject, reason);
            }
        }
        return Optional.empty();
    }

    private <T> List<T> firstList(String op, String subject, Function<MarketDataSource, List<T>> call) {
        return first(op, subject, source -> {
            List<T> list = call.apply(source);
            return list == null || list.isEmpty() ? Optional.<List<T>>empty() : Optional.of(list);
        }).orElse(List.of());
    }
}
```

`backend/marketdata/src/main/java/com/finrisk/marketdata/CachingMarketData.java`:

```java
package com.finrisk.marketdata;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;

import java.math.BigDecimal;
import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.Optional;

/** In-process cache in front of any MarketData. Only successful, non-empty answers are cached. */
public final class CachingMarketData implements MarketData {

    public record Ttls(Duration prices, Duration profile, Duration etf, Duration quote, Duration fundamentals, Duration ratios) {
        public static Ttls defaults() {
            return new Ttls(Duration.ofMinutes(15), Duration.ofHours(6), Duration.ofHours(12),
                    Duration.ofMinutes(5), Duration.ofHours(6), Duration.ofHours(1));
        }
    }

    private static final long MAX_ENTRIES = 5_000;

    private final MarketData delegate;
    private final Cache<String, List<PricePoint>> prices;
    private final Cache<String, CompanyProfile> profiles;
    private final Cache<String, List<EtfHolding>> etfs;
    private final Cache<String, Quote> quotes;
    private final Cache<String, Fundamentals> fundamentals;
    private final Cache<String, BigDecimal> metrics;
    private final Cache<String, List<Peer>> peers;

    public CachingMarketData(MarketData delegate, Ttls ttls) {
        this.delegate = delegate;
        this.prices = cache(ttls.prices());
        this.profiles = cache(ttls.profile());
        this.etfs = cache(ttls.etf());
        this.quotes = cache(ttls.quote());
        this.fundamentals = cache(ttls.fundamentals());
        this.metrics = cache(ttls.ratios());
        this.peers = cache(ttls.ratios());
    }

    @Override
    public List<PricePoint> fetchDailyPrices(String symbol, int days) {
        String key = key(symbol) + "|" + days;
        List<PricePoint> hit = prices.getIfPresent(key);
        if (hit != null) return hit;
        List<PricePoint> fresh = delegate.fetchDailyPrices(symbol, days);
        if (!fresh.isEmpty()) prices.put(key, fresh);
        return fresh;
    }

    @Override
    public CompanyProfile fetchProfile(String symbol) {
        String key = key(symbol);
        CompanyProfile hit = profiles.getIfPresent(key);
        if (hit != null) return hit;
        CompanyProfile fresh = delegate.fetchProfile(symbol);
        if (!"Unknown".equals(fresh.sector())) profiles.put(key, fresh);
        return fresh;
    }

    @Override
    public List<EtfHolding> fetchEtfHoldings(String etfSymbol) {
        String key = key(etfSymbol);
        List<EtfHolding> hit = etfs.getIfPresent(key);
        if (hit != null) return hit;
        List<EtfHolding> fresh = delegate.fetchEtfHoldings(etfSymbol);
        if (!fresh.isEmpty()) etfs.put(key, fresh);
        return fresh;
    }

    @Override
    public Optional<Quote> fetchQuote(String symbol) {
        String key = key(symbol);
        Quote hit = quotes.getIfPresent(key);
        if (hit != null) return Optional.of(hit);
        Optional<Quote> fresh = delegate.fetchQuote(symbol);
        fresh.ifPresent(v -> quotes.put(key, v));
        return fresh;
    }

    @Override
    public Optional<Fundamentals> fetchFundamentals(String symbol) {
        String key = key(symbol);
        Fundamentals hit = fundamentals.getIfPresent(key);
        if (hit != null) return Optional.of(hit);
        Optional<Fundamentals> fresh = delegate.fetchFundamentals(symbol);
        fresh.ifPresent(v -> fundamentals.put(key, v));
        return fresh;
    }

    @Override
    public Optional<BigDecimal> fetchMetric(String symbol, ValuationMetric metric) {
        String key = key(symbol) + "|" + metric;
        BigDecimal hit = metrics.getIfPresent(key);
        if (hit != null) return Optional.of(hit);
        Optional<BigDecimal> fresh = delegate.fetchMetric(symbol, metric);
        fresh.ifPresent(v -> metrics.put(key, v));
        return fresh;
    }

    @Override
    public List<Peer> fetchPeers(String sector, int limit) {
        String key = key(sector) + "|" + limit;
        List<Peer> hit = peers.getIfPresent(key);
        if (hit != null) return hit;
        List<Peer> fresh = delegate.fetchPeers(sector, limit);
        if (!fresh.isEmpty()) peers.put(key, fresh);
        return fresh;
    }

    private static <V> Cache<String, V> cache(Duration ttl) {
        return Caffeine.newBuilder().expireAfterWrite(ttl).maximumSize(MAX_ENTRIES).build();
    }

    private static String key(String value) {
        return String.valueOf(value).trim().toUpperCase(Locale.ROOT);
    }
}
```

`backend/marketdata/src/main/java/com/finrisk/marketdata/MarketDataProperties.java`:

```java
package com.finrisk.marketdata;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

import java.util.List;

/** {@code marketdata.sources} is the order sources are tried in. */
@ConfigurationProperties(prefix = "marketdata")
public record MarketDataProperties(
        @DefaultValue({"fmp", "yahoo"}) List<String> sources,
        @DefaultValue Fmp fmp,
        @DefaultValue Yahoo yahoo) {

    public record Fmp(
            @DefaultValue("") String apiKey,
            @DefaultValue("https://financialmodelingprep.com/api/v3") String baseUrl) {}

    public record Yahoo(@DefaultValue("true") boolean enabled) {}
}
```

`backend/marketdata/src/main/java/com/finrisk/marketdata/MarketDataConfiguration.java`:

```java
package com.finrisk.marketdata;

import com.finrisk.marketdata.fmp.FmpSource;
import com.finrisk.marketdata.source.HttpFetcher;
import com.finrisk.marketdata.source.JdkHttpFetcher;
import com.finrisk.marketdata.source.MarketDataSource;
import com.finrisk.marketdata.yahoo.YahooSource;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;

/** Builds the one MarketData bean the rest of the app sees: cache -> failover -> sources. */
@Configuration
@EnableConfigurationProperties(MarketDataProperties.class)
public class MarketDataConfiguration {

    @Bean
    MarketData marketData(MarketDataProperties properties) {
        return build(properties, JdkHttpFetcher::new, Clock.systemUTC());
    }

    static MarketData build(MarketDataProperties properties, Supplier<HttpFetcher> fetchers, Clock clock) {
        List<MarketDataSource> sources = new ArrayList<>();
        for (String name : properties.sources()) {
            switch (name.trim().toLowerCase()) {
                case "fmp" -> sources.add(new FmpSource(
                        properties.fmp().apiKey(), properties.fmp().baseUrl(), fetchers.get(), clock));
                case "yahoo" -> {
                    if (properties.yahoo().enabled()) {
                        sources.add(new YahooSource(fetchers.get(), clock));
                    }
                }
                default -> throw new IllegalArgumentException("Unknown market data source: " + name);
            }
        }
        return new CachingMarketData(new FailoverMarketData(sources), CachingMarketData.Ttls.defaults());
    }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && mvn -B -pl marketdata -am test`
Expected: `FailoverMarketDataTest` 9 tests, `CachingMarketDataTest` 5, `MarketDataConfigurationTest` 3, plus earlier ones; no failures; `BUILD SUCCESS`.

- [ ] **Step 7: Commit**

```bash
git add backend/marketdata
git commit -m "feat(marketdata): failover, caching and Spring wiring"
```

---
