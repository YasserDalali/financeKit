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
      portfolio/    domain (model, exception, repository ports, Holding and other read models)
                    application (account, asset, transaction, user, portfolio, P&L services, mapper, factory)
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
- Create: `backend/pom.xml`, `backend/.gitignore`
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

`backend/.gitignore` (so build output never gets committed by the later `git add backend/...` steps):

```gitignore
target/
.idea/
*.iml
```

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
git add backend/.gitignore backend/pom.xml backend/marketdata-api
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
Expected: `Tests run: 13` for `FmpSourceTest` (the `marketdata` module line) and `Tests run: 6` for `marketdata-api`, no failures, `BUILD SUCCESS`.

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

## Phase B: Valuation context

### Task 5: Valuation domain models

**Files:**
- Modify: `backend/pom.xml` (add `<module>valuation</module>`)
- Create: `backend/valuation/pom.xml`
- Create: `backend/valuation/src/main/java/com/finrisk/valuation/domain/{Rates,GrowthStage,DcfInput,DcfResult,DcfModel,DdmInput,DdmResult,DdmModel,LynchInput,LynchResult,LynchModel,ValuationSignal,InsufficientPeerDataException,PeerStats,Verdict}.java`
- Test: `backend/valuation/src/test/java/com/finrisk/valuation/domain/{DcfModelTest,DdmModelTest,LynchModelTest,PeerStatsTest,VerdictTest}.java`

**Interfaces:**
- Consumes: nothing from other tasks (pure Java; the module depends on `marketdata-api` for Task 6).
- Produces:
  - `Rates.requireDiscountAboveTerminal(double discountRate, double terminalGrowthRate)` throws `IllegalArgumentException("discountRate must be greater than terminalGrowthRate")`
  - `record GrowthStage(int years, double rate)` (years 1..100)
  - `record DcfInput(double fcf, double sharesOutstanding, List<GrowthStage> stages, double discountRate, double terminalGrowthRate, Double price)`; `record DcfResult(double intrinsicValue, double pvTerminal, double pvFcf, Double upside)`; `DcfModel.compute(DcfInput) -> DcfResult`
  - `record DdmInput(double dividendPerShare, double discountRate, double terminalGrowthRate, Integer highGrowthYears, Double highGrowthRate, Double price)`; `record DdmResult(double intrinsicValue, double pvDividends, double pvTerminal, Double upside)`; `DdmModel.compute(DdmInput) -> DdmResult`
  - `record LynchInput(double eps, double growthRate, Double price, double dividendYield)`; `record LynchResult(double fairValue, Double pe, Double peg, Double lynchRatio, Double upside)`; `LynchModel.compute(LynchInput) -> LynchResult`
  - `enum ValuationSignal { UNDERVALUED, FAIRLY_VALUED, OVERVALUED }`; `class InsufficientPeerDataException extends IllegalStateException`
  - `PeerStats.of(List<Double>) -> PeerStats` with `quartiles() -> PeerStats.Quartiles(double q1, double median, double q3)` and `signal(double) -> ValuationSignal`
  - `enum Verdict { STRONG_BUY, BUY, WEAK_BUY, SLIGHT_BUY, HOLD, SLIGHT_SELL, WEAK_SELL, SELL, STRONG_SELL; static Verdict of(ValuationSignal, Double upside) }`

- [ ] **Step 1: Register the module and create its POM**

In `backend/pom.xml` set:

```xml
  <modules>
    <module>marketdata-api</module>
    <module>marketdata</module>
    <module>valuation</module>
  </modules>
```

`backend/valuation/pom.xml`:

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
  <artifactId>valuation</artifactId>
  <description>Valuation context: DCF, dividend discount, Lynch fair value, peer comparison. Sees market data only through MarketData.</description>

  <dependencies>
    <dependency>
      <groupId>com.finrisk</groupId>
      <artifactId>marketdata-api</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 2: Write the failing tests** (expected values are worked out by hand in the comments)

`backend/valuation/src/test/java/com/finrisk/valuation/domain/DcfModelTest.java`:

```java
package com.finrisk.valuation.domain;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

class DcfModelTest {

    @Test
    void flatCashFlowsAtTenPercentAreWorthParValue() {
        // pvFcf = 100/1.1 + 100/1.21 = 173.5537; terminal = 100/0.10 = 1000, pv = 1000/1.21 = 826.4463; total 1000; per share (10) = 100
        DcfResult r = DcfModel.compute(new DcfInput(100, 10, List.of(new GrowthStage(2, 0.0)), 0.10, 0.0, 80.0));

        assertThat(r.intrinsicValue()).isCloseTo(100.0, within(1e-9));
        assertThat(r.pvFcf()).isCloseTo(173.5537190082645, within(1e-6));
        assertThat(r.pvTerminal()).isCloseTo(826.4462809917355, within(1e-6));
        assertThat(r.upside()).isCloseTo(0.25, within(1e-9));
    }

    @Test
    void eachStageAppliesItsOwnRateInOrder() {
        // year 1 grows 10% (110), year 2 flat (110): pvFcf = 100 + 90.9091; terminal = 110/0.10 = 1100, pv = 909.0909; total 1100
        DcfResult r = DcfModel.compute(new DcfInput(
                100, 1, List.of(new GrowthStage(1, 0.10), new GrowthStage(1, 0.0)), 0.10, 0.0, null));

        assertThat(r.intrinsicValue()).isCloseTo(1100.0, within(1e-6));
        assertThat(r.upside()).isNull();
    }

    @Test
    void rejectsDiscountRateAtOrBelowTerminalGrowth() {
        assertThatThrownBy(() -> new DcfInput(100, 10, List.of(new GrowthStage(1, 0)), 0.03, 0.03, null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("discountRate must be greater than terminalGrowthRate");
    }

    @Test
    void rejectsNonPositiveSharesAndEmptyStages() {
        assertThatThrownBy(() -> new DcfInput(100, 0, List.of(new GrowthStage(1, 0)), 0.10, 0.02, null))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("sharesOutstanding");
        assertThatThrownBy(() -> new DcfInput(100, 10, List.of(), 0.10, 0.02, null))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("growth stage");
    }

    @Test
    void stageYearsMustBeBetweenOneAndOneHundred() {
        assertThatThrownBy(() -> new GrowthStage(0, 0.1)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new GrowthStage(101, 0.1)).isInstanceOf(IllegalArgumentException.class);
    }
}
```

`backend/valuation/src/test/java/com/finrisk/valuation/domain/DdmModelTest.java`:

```java
package com.finrisk.valuation.domain;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

class DdmModelTest {

    @Test
    void gordonGrowthWhenNoHighGrowthStage() {
        // D0 = 2.00, r = 8%, g = 3%: 2.00 * 1.03 / 0.05 = 41.20
        DdmResult r = DdmModel.compute(new DdmInput(2.0, 0.08, 0.03, null, null, 20.0));

        assertThat(r.intrinsicValue()).isCloseTo(41.2, within(1e-9));
        assertThat(r.pvDividends()).isZero();
        assertThat(r.pvTerminal()).isCloseTo(41.2, within(1e-9));
        assertThat(r.upside()).isCloseTo(1.06, within(1e-9));
    }

    @Test
    void twoStageDiscountsTheHighGrowthDividendsThenTheTerminalValue() {
        // D0 = 1, 2 years at 10%: dividends 1.10 and 1.21, each worth 1.00 today; terminal 1.21*1.02/0.08 = 15.4275, pv = 12.75
        DdmResult r = DdmModel.compute(new DdmInput(1.0, 0.10, 0.02, 2, 0.10, null));

        assertThat(r.pvDividends()).isCloseTo(2.0, within(1e-9));
        assertThat(r.pvTerminal()).isCloseTo(12.75, within(1e-9));
        assertThat(r.intrinsicValue()).isCloseTo(14.75, within(1e-9));
        assertThat(r.upside()).isNull();
    }

    @Test
    void validatesItsInputs() {
        assertThatThrownBy(() -> new DdmInput(0, 0.08, 0.03, null, null, null))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("dividendPerShare");
        assertThatThrownBy(() -> new DdmInput(2, 0.03, 0.03, null, null, null))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("discountRate");
        assertThatThrownBy(() -> new DdmInput(2, 0.08, 0.03, 2, null, null))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("together");
        assertThatThrownBy(() -> new DdmInput(2, 0.08, 0.03, null, 0.1, null))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("together");
        assertThatThrownBy(() -> new DdmInput(2, 0.08, 0.03, 101, 0.1, null))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("highGrowthYears");
    }
}
```

`backend/valuation/src/test/java/com/finrisk/valuation/domain/LynchModelTest.java`:

```java
package com.finrisk.valuation.domain;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

class LynchModelTest {

    @Test
    void fairValueIsEpsTimesGrowthPercent() {
        // EPS 5, growth 20%: fair value 100; price 80 => PE 16, PEG 0.8, ratio (20+0)/16 = 1.25, upside 25%
        LynchResult r = LynchModel.compute(new LynchInput(5.0, 0.20, 80.0, 0.0));

        assertThat(r.fairValue()).isCloseTo(100.0, within(1e-9));
        assertThat(r.pe()).isCloseTo(16.0, within(1e-9));
        assertThat(r.peg()).isCloseTo(0.8, within(1e-9));
        assertThat(r.lynchRatio()).isCloseTo(1.25, within(1e-9));
        assertThat(r.upside()).isCloseTo(0.25, within(1e-9));
    }

    @Test
    void dividendYieldRaisesTheLynchRatio() {
        // (20 + 2) / 16 = 1.375
        LynchResult r = LynchModel.compute(new LynchInput(5.0, 0.20, 80.0, 0.02));

        assertThat(r.lynchRatio()).isCloseTo(1.375, within(1e-9));
    }

    @Test
    void withoutAPriceOnlyTheFairValueIsKnown() {
        LynchResult r = LynchModel.compute(new LynchInput(5.0, 0.20, null, 0.0));

        assertThat(r.fairValue()).isCloseTo(100.0, within(1e-9));
        assertThat(r.pe()).isNull();
        assertThat(r.peg()).isNull();
        assertThat(r.lynchRatio()).isNull();
        assertThat(r.upside()).isNull();
    }

    @Test
    void epsAndGrowthMustBePositive() {
        assertThatThrownBy(() -> new LynchInput(0, 0.2, null, 0)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new LynchInput(5, 0, null, 0)).isInstanceOf(IllegalArgumentException.class);
    }
}
```

`backend/valuation/src/test/java/com/finrisk/valuation/domain/PeerStatsTest.java`:

```java
package com.finrisk.valuation.domain;

import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

class PeerStatsTest {

    private static final List<Double> VALUES = List.of(5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0);

    @Test
    void quartilesUseLinearInterpolation() {
        PeerStats.Quartiles q = PeerStats.of(VALUES).quartiles();

        assertThat(q.q1()).isCloseTo(16.25, within(1e-9));
        assertThat(q.median()).isCloseTo(27.5, within(1e-9));
        assertThat(q.q3()).isCloseTo(38.75, within(1e-9));
    }

    @Test
    void signalIsBelowQ1UnderBetweenFairAboveQ3Over() {
        PeerStats stats = PeerStats.of(VALUES);

        assertThat(stats.signal(4)).isEqualTo(ValuationSignal.UNDERVALUED);
        assertThat(stats.signal(27.5)).isEqualTo(ValuationSignal.FAIRLY_VALUED);
        assertThat(stats.signal(50)).isEqualTo(ValuationSignal.OVERVALUED);
    }

    @Test
    void needsAtLeastFourValidValues() {
        assertThatThrownBy(() -> PeerStats.of(List.of(1.0, 2.0, 3.0)))
                .isInstanceOf(InsufficientPeerDataException.class)
                .hasMessageContaining("Not enough peer data");
    }

    @Test
    void nullsAndNaNsAreIgnored() {
        List<Double> mixed = Arrays.asList(null, 5.0, Double.NaN, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0);

        assertThat(PeerStats.of(mixed).quartiles().median()).isCloseTo(22.5, within(1e-9));
    }
}
```

`backend/valuation/src/test/java/com/finrisk/valuation/domain/VerdictTest.java`:

```java
package com.finrisk.valuation.domain;

import org.junit.jupiter.api.Test;

import static com.finrisk.valuation.domain.ValuationSignal.FAIRLY_VALUED;
import static com.finrisk.valuation.domain.ValuationSignal.OVERVALUED;
import static com.finrisk.valuation.domain.ValuationSignal.UNDERVALUED;
import static org.assertj.core.api.Assertions.assertThat;

class VerdictTest {

    @Test
    void combinesPeerSignalWithDcfUpside() {
        assertThat(Verdict.of(UNDERVALUED, 0.20)).isEqualTo(Verdict.STRONG_BUY);
        assertThat(Verdict.of(UNDERVALUED, 0.0)).isEqualTo(Verdict.BUY);
        assertThat(Verdict.of(UNDERVALUED, -0.20)).isEqualTo(Verdict.WEAK_BUY);
        assertThat(Verdict.of(FAIRLY_VALUED, 0.20)).isEqualTo(Verdict.SLIGHT_BUY);
        assertThat(Verdict.of(FAIRLY_VALUED, 0.0)).isEqualTo(Verdict.HOLD);
        assertThat(Verdict.of(FAIRLY_VALUED, -0.20)).isEqualTo(Verdict.SLIGHT_SELL);
        assertThat(Verdict.of(OVERVALUED, 0.20)).isEqualTo(Verdict.WEAK_SELL);
        assertThat(Verdict.of(OVERVALUED, 0.0)).isEqualTo(Verdict.SELL);
        assertThat(Verdict.of(OVERVALUED, -0.20)).isEqualTo(Verdict.STRONG_SELL);
    }

    @Test
    void exactlyTenPercentUpsideIsNotAboveTheThreshold() {
        assertThat(Verdict.of(UNDERVALUED, 0.10)).isEqualTo(Verdict.BUY);
        assertThat(Verdict.of(UNDERVALUED, -0.10)).isEqualTo(Verdict.WEAK_BUY);
    }

    @Test
    void anUnknownUpsideCountsAsZero() {
        assertThat(Verdict.of(FAIRLY_VALUED, null)).isEqualTo(Verdict.HOLD);
    }
}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && mvn -B -pl valuation -am test`
Expected: FAIL, compilation errors "cannot find symbol: class DcfModel / DdmInput / LynchInput / PeerStats / Verdict".

- [ ] **Step 4: Write the implementation**

All files are in `backend/valuation/src/main/java/com/finrisk/valuation/domain/`.

`Rates.java`:

```java
package com.finrisk.valuation.domain;

/** Shared rate rules, so the web layer, the service and the models all say the same thing. */
public final class Rates {

    private Rates() {}

    public static void requireDiscountAboveTerminal(double discountRate, double terminalGrowthRate) {
        if (!(discountRate > terminalGrowthRate)) {
            throw new IllegalArgumentException("discountRate must be greater than terminalGrowthRate");
        }
    }
}
```

`GrowthStage.java`:

```java
package com.finrisk.valuation.domain;

/** {@code years} of cash-flow growth at {@code rate} (0.10 = 10%). */
public record GrowthStage(int years, double rate) {

    public GrowthStage {
        if (years < 1 || years > 100) {
            throw new IllegalArgumentException("stage years must be between 1 and 100");
        }
    }
}
```

`DcfInput.java`:

```java
package com.finrisk.valuation.domain;

import java.util.List;

public record DcfInput(
        double fcf,
        double sharesOutstanding,
        List<GrowthStage> stages,
        double discountRate,
        double terminalGrowthRate,
        Double price) {

    public DcfInput {
        if (!(sharesOutstanding > 0)) {
            throw new IllegalArgumentException("sharesOutstanding must be positive");
        }
        if (stages == null || stages.isEmpty()) {
            throw new IllegalArgumentException("at least one growth stage is required");
        }
        Rates.requireDiscountAboveTerminal(discountRate, terminalGrowthRate);
        stages = List.copyOf(stages);
    }
}
```

`DcfResult.java`:

```java
package com.finrisk.valuation.domain;

/** {@code pvTerminal} is the present value of the terminal value. {@code upside} is null when no price is known. */
public record DcfResult(double intrinsicValue, double pvTerminal, double pvFcf, Double upside) {}
```

`DcfModel.java`:

```java
package com.finrisk.valuation.domain;

/** Multi-stage discounted cash flow, per share. */
public final class DcfModel {

    private DcfModel() {}

    public static DcfResult compute(DcfInput in) {
        double pvFcf = 0;
        double current = in.fcf();
        int t = 0;
        for (GrowthStage stage : in.stages()) {
            for (int y = 0; y < stage.years(); y++) {
                t++;
                current *= 1 + stage.rate();
                pvFcf += current / Math.pow(1 + in.discountRate(), t);
            }
        }
        double terminal = current * (1 + in.terminalGrowthRate()) / (in.discountRate() - in.terminalGrowthRate());
        double pvTerminal = terminal / Math.pow(1 + in.discountRate(), t);
        double intrinsic = (pvFcf + pvTerminal) / in.sharesOutstanding();
        Double upside = in.price() != null && in.price() > 0 ? (intrinsic - in.price()) / in.price() : null;
        return new DcfResult(intrinsic, pvTerminal, pvFcf, upside);
    }
}
```

`DdmInput.java`:

```java
package com.finrisk.valuation.domain;

/**
 * {@code dividendPerShare} is the latest annual dividend (D0). Give both {@code highGrowthYears} and
 * {@code highGrowthRate} for a two-stage model, or neither for Gordon growth.
 */
public record DdmInput(
        double dividendPerShare,
        double discountRate,
        double terminalGrowthRate,
        Integer highGrowthYears,
        Double highGrowthRate,
        Double price) {

    public DdmInput {
        if (!(dividendPerShare > 0)) {
            throw new IllegalArgumentException("dividendPerShare must be positive");
        }
        Rates.requireDiscountAboveTerminal(discountRate, terminalGrowthRate);
        if ((highGrowthYears == null) != (highGrowthRate == null)) {
            throw new IllegalArgumentException("highGrowthYears and highGrowthRate must be provided together");
        }
        if (highGrowthYears != null && (highGrowthYears < 1 || highGrowthYears > 100)) {
            throw new IllegalArgumentException("highGrowthYears must be between 1 and 100");
        }
    }
}
```

`DdmResult.java`:

```java
package com.finrisk.valuation.domain;

public record DdmResult(double intrinsicValue, double pvDividends, double pvTerminal, Double upside) {}
```

`DdmModel.java`:

```java
package com.finrisk.valuation.domain;

/** Dividend discount model: Gordon growth, or two-stage when a high-growth period is given. */
public final class DdmModel {

    private DdmModel() {}

    public static DdmResult compute(DdmInput in) {
        boolean twoStage = in.highGrowthYears() != null;
        int years = twoStage ? in.highGrowthYears() : 0;
        double growth = twoStage ? in.highGrowthRate() : in.terminalGrowthRate();
        double r = in.discountRate();
        double g = in.terminalGrowthRate();

        double pvDividends = 0;
        double dividend = in.dividendPerShare();
        for (int t = 1; t <= years; t++) {
            dividend *= 1 + growth;
            pvDividends += dividend / Math.pow(1 + r, t);
        }
        double pvTerminal = dividend * (1 + g) / (r - g) / Math.pow(1 + r, years);
        double intrinsic = pvDividends + pvTerminal;
        Double upside = in.price() != null && in.price() > 0 ? (intrinsic - in.price()) / in.price() : null;
        return new DdmResult(intrinsic, pvDividends, pvTerminal, upside);
    }
}
```

`LynchInput.java`:

```java
package com.finrisk.valuation.domain;

/** {@code growthRate} and {@code dividendYield} are decimals (0.15 = 15%). */
public record LynchInput(double eps, double growthRate, Double price, double dividendYield) {

    public LynchInput {
        if (!(eps > 0)) {
            throw new IllegalArgumentException("eps must be positive");
        }
        if (!(growthRate > 0)) {
            throw new IllegalArgumentException("growthRate must be positive");
        }
    }
}
```

`LynchResult.java`:

```java
package com.finrisk.valuation.domain;

/** Everything except {@code fairValue} is null when no usable price is known. */
public record LynchResult(double fairValue, Double pe, Double peg, Double lynchRatio, Double upside) {}
```

`LynchModel.java`:

```java
package com.finrisk.valuation.domain;

/** Peter Lynch fair value: a fair P/E equals the growth rate in percent (PEG = 1). */
public final class LynchModel {

    private LynchModel() {}

    public static LynchResult compute(LynchInput in) {
        double growthPercent = in.growthRate() * 100;
        double fairValue = in.eps() * growthPercent;
        Double price = in.price();
        if (price == null || !(price > 0)) {
            return new LynchResult(fairValue, null, null, null, null);
        }
        double pe = price / in.eps();
        return new LynchResult(
                fairValue,
                pe,
                pe / growthPercent,
                (growthPercent + in.dividendYield() * 100) / pe,
                (fairValue - price) / price);
    }
}
```

`ValuationSignal.java`:

```java
package com.finrisk.valuation.domain;

public enum ValuationSignal { UNDERVALUED, FAIRLY_VALUED, OVERVALUED }
```

`InsufficientPeerDataException.java`:

```java
package com.finrisk.valuation.domain;

public class InsufficientPeerDataException extends IllegalStateException {

    public InsufficientPeerDataException(String message) {
        super(message);
    }
}
```

`PeerStats.java`:

```java
package com.finrisk.valuation.domain;

import java.util.List;

/** Where a value sits among its peers: quartiles with linear interpolation. */
public final class PeerStats {

    public record Quartiles(double q1, double median, double q3) {}

    private static final int MINIMUM_VALUES = 4;

    private final Quartiles quartiles;

    private PeerStats(Quartiles quartiles) {
        this.quartiles = quartiles;
    }

    public static PeerStats of(List<Double> values) {
        double[] sorted = values.stream()
                .filter(v -> v != null && !v.isNaN())
                .mapToDouble(Double::doubleValue)
                .sorted()
                .toArray();
        if (sorted.length < MINIMUM_VALUES) {
            throw new InsufficientPeerDataException(
                    "Not enough peer data: " + sorted.length + " valid values, need at least " + MINIMUM_VALUES);
        }
        return new PeerStats(new Quartiles(quantile(sorted, 0.25), quantile(sorted, 0.5), quantile(sorted, 0.75)));
    }

    public Quartiles quartiles() {
        return quartiles;
    }

    public ValuationSignal signal(double value) {
        if (value < quartiles.q1()) return ValuationSignal.UNDERVALUED;
        if (value > quartiles.q3()) return ValuationSignal.OVERVALUED;
        return ValuationSignal.FAIRLY_VALUED;
    }

    private static double quantile(double[] sorted, double p) {
        double position = p * (sorted.length - 1);
        int low = (int) Math.floor(position);
        int high = (int) Math.ceil(position);
        if (low == high) return sorted[low];
        return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
    }
}
```

`Verdict.java`:

```java
package com.finrisk.valuation.domain;

/** Peer-relative signal combined with DCF upside. Upside beyond +/-10% moves the call one notch. */
public enum Verdict {
    STRONG_BUY, BUY, WEAK_BUY, SLIGHT_BUY, HOLD, SLIGHT_SELL, WEAK_SELL, SELL, STRONG_SELL;

    private static final double THRESHOLD = 0.10;

    /** A null upside (no price known) counts as zero. */
    public static Verdict of(ValuationSignal signal, Double upside) {
        double u = upside == null ? 0.0 : upside;
        return switch (signal) {
            case UNDERVALUED -> u > THRESHOLD ? STRONG_BUY : u > -THRESHOLD ? BUY : WEAK_BUY;
            case FAIRLY_VALUED -> u > THRESHOLD ? SLIGHT_BUY : u > -THRESHOLD ? HOLD : SLIGHT_SELL;
            case OVERVALUED -> u > THRESHOLD ? WEAK_SELL : u > -THRESHOLD ? SELL : STRONG_SELL;
        };
    }
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && mvn -B -pl valuation -am test`
Expected: the `valuation` module reports `Tests run: 19` (DcfModelTest 5, DdmModelTest 3, LynchModelTest 4, PeerStatsTest 4, VerdictTest 3), no failures, `BUILD SUCCESS`.

- [ ] **Step 6: Commit**

```bash
git add backend/pom.xml backend/valuation
git commit -m "feat(valuation): DCF, DDM, Lynch, peer stats and verdict domain models"
```

---

### Task 6: Valuation application service

**Files:**
- Create: `backend/valuation/src/main/java/com/finrisk/valuation/application/{TickerNotFoundException,ValuationNotApplicableException,DcfCommand,DdmCommand,LynchCommand,PeerCommand,CompareCommand,DcfOutcome,DdmOutcome,LynchOutcome,PeerOutcome,CompareOutcome,ValuationService}.java`
- Test: `backend/valuation/src/test/java/com/finrisk/valuation/support/FakeMarketData.java`
- Test: `backend/valuation/src/test/java/com/finrisk/valuation/application/ValuationServiceTest.java`

**Interfaces:**
- Consumes: `MarketData`, `Quote`, `Fundamentals`, `CompanyProfile`, `Peer`, `ValuationMetric` (Task 1); every domain type from Task 5.
- Produces:
  - `record DcfCommand(String ticker, Double fcf, Double sharesOutstanding, Double growthRate, int projectionYears, List<GrowthStage> stages, double discountRate, double terminalGrowthRate)`
  - `record DdmCommand(String ticker, Double dividendPerShare, double discountRate, double terminalGrowthRate, Integer highGrowthYears, Double highGrowthRate)`
  - `record LynchCommand(String ticker, Double eps, Double growthRate, Double dividendPerShare)`
  - `record PeerCommand(String ticker, ValuationMetric metric)`; `record CompareCommand(PeerCommand peer, DcfCommand dcf)`
  - `record DcfOutcome(String ticker, Double price, DcfResult result)`; `record DdmOutcome(String ticker, Double price, double dividendPerShare, String model, DdmResult result)`; `record LynchOutcome(String ticker, Double price, double eps, double growthRate, LynchResult result)`; `record PeerOutcome(String ticker, String sector, ValuationMetric metric, double value, PeerStats.Quartiles quartiles, ValuationSignal signal)`; `record CompareOutcome(PeerOutcome peer, Double price, DcfResult dcf, Verdict verdict)`
  - `@Service class ValuationService { ValuationService(MarketData); DcfOutcome dcf(DcfCommand); DdmOutcome ddm(DdmCommand); LynchOutcome lynch(LynchCommand); PeerOutcome analyze(PeerCommand); CompareOutcome compare(CompareCommand) }`
  - `TickerNotFoundException(String ticker)` (HTTP 404), `ValuationNotApplicableException(String message)` (HTTP 422); `InsufficientPeerDataException` from Task 5 also maps to 422.
  - Test helper `FakeMarketData` (public, public fields `quotes`, `fundamentals`, `profiles`, `peers`, and `metric(symbol, metric, value)`).

- [ ] **Step 1: Write the test helper and the failing service tests**

`backend/valuation/src/test/java/com/finrisk/valuation/support/FakeMarketData.java`:

```java
package com.finrisk.valuation.support;

import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.EtfHolding;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.MarketData;
import com.finrisk.marketdata.Peer;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** In-memory MarketData for tests. */
public final class FakeMarketData implements MarketData {

    public final Map<String, Quote> quotes = new HashMap<>();
    public final Map<String, Fundamentals> fundamentals = new HashMap<>();
    public final Map<String, CompanyProfile> profiles = new HashMap<>();
    public final List<Peer> peers = new ArrayList<>();
    private final Map<String, BigDecimal> metrics = new HashMap<>();

    public FakeMarketData metric(String symbol, ValuationMetric metric, String value) {
        metrics.put(symbol + "|" + metric, new BigDecimal(value));
        return this;
    }

    @Override public List<PricePoint> fetchDailyPrices(String symbol, int days) { return List.of(); }

    @Override public CompanyProfile fetchProfile(String symbol) {
        return profiles.getOrDefault(symbol, CompanyProfile.unknown(symbol));
    }

    @Override public List<EtfHolding> fetchEtfHoldings(String etfSymbol) { return List.of(); }

    @Override public Optional<Quote> fetchQuote(String symbol) { return Optional.ofNullable(quotes.get(symbol)); }

    @Override public Optional<Fundamentals> fetchFundamentals(String symbol) {
        return Optional.ofNullable(fundamentals.get(symbol));
    }

    @Override public Optional<BigDecimal> fetchMetric(String symbol, ValuationMetric metric) {
        return Optional.ofNullable(metrics.get(symbol + "|" + metric));
    }

    @Override public List<Peer> fetchPeers(String sector, int limit) { return peers; }
}
```

`backend/valuation/src/test/java/com/finrisk/valuation/application/ValuationServiceTest.java`:

```java
package com.finrisk.valuation.application;

import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.Peer;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;
import com.finrisk.valuation.domain.GrowthStage;
import com.finrisk.valuation.domain.InsufficientPeerDataException;
import com.finrisk.valuation.domain.ValuationSignal;
import com.finrisk.valuation.domain.Verdict;
import com.finrisk.valuation.support.FakeMarketData;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

class ValuationServiceTest {

    private final FakeMarketData data = new FakeMarketData();
    private final ValuationService service = new ValuationService(data);

    @BeforeEach
    void quoteForAapl() {
        data.quotes.put("AAPL", new Quote("AAPL", new BigDecimal("80"), new BigDecimal("10"), new BigDecimal("2.0")));
    }

    private static DcfCommand dcf(Double fcf, Double shares) {
        return new DcfCommand("AAPL", fcf, shares, 0.0, 2, null, 0.10, 0.0);
    }

    // ---- DCF

    @Test
    void dcfUsesTheFiguresInTheRequest() {
        DcfOutcome out = service.dcf(new DcfCommand(
                "AAPL", 100.0, 10.0, null, 2, List.of(new GrowthStage(2, 0.0)), 0.10, 0.0));

        assertThat(out.ticker()).isEqualTo("AAPL");
        assertThat(out.price()).isEqualTo(80.0);
        assertThat(out.result().intrinsicValue()).isCloseTo(100.0, within(1e-9));
        assertThat(out.result().upside()).isCloseTo(0.25, within(1e-9));
    }

    @Test
    void dcfFillsMissingFigureFromFundamentalsAndBuildsOneStageFromTheGrowthRate() {
        data.fundamentals.put("AAPL", new Fundamentals(new BigDecimal("100"), new BigDecimal("10"), null, null));

        DcfOutcome out = service.dcf(dcf(null, null));

        assertThat(out.result().intrinsicValue()).isCloseTo(100.0, within(1e-9));
    }

    @Test
    void dcfFallsBackToTheQuoteForSharesWhenFundamentalsLackThem() {
        data.fundamentals.put("AAPL", new Fundamentals(new BigDecimal("100"), null, null, null));

        assertThat(service.dcf(dcf(null, null)).result().intrinsicValue()).isCloseTo(100.0, within(1e-9));
    }

    @Test
    void dcfRejectsNonPositiveFreeCashFlow() {
        assertThatThrownBy(() -> service.dcf(dcf(-5.0, 10.0)))
                .isInstanceOf(ValuationNotApplicableException.class)
                .hasMessageContaining("positive");
    }

    @Test
    void dcfWithoutAnyCashFlowDataIsNotApplicable() {
        assertThatThrownBy(() -> service.dcf(dcf(null, null)))
                .isInstanceOf(ValuationNotApplicableException.class);
    }

    @Test
    void ratesAreCheckedBeforeAnyDataIsFetched() {
        FakeMarketData empty = new FakeMarketData(); // no quote: a fetch would give TickerNotFound
        assertThatThrownBy(() -> new ValuationService(empty).dcf(
                new DcfCommand("ZZZ", 100.0, 10.0, 0.0, 2, null, 0.02, 0.03)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("discountRate");
    }

    @Test
    void anUnknownTickerIsNotFound() {
        assertThatThrownBy(() -> service.dcf(new DcfCommand("ZZZ", 100.0, 10.0, 0.0, 2, null, 0.10, 0.0)))
                .isInstanceOf(TickerNotFoundException.class)
                .hasMessageContaining("ZZZ");
    }

    // ---- DDM

    @Test
    void ddmUsesTheQuoteDividendWhenNoneIsGiven() {
        DdmOutcome out = service.ddm(new DdmCommand("AAPL", null, 0.08, 0.03, null, null));

        assertThat(out.model()).isEqualTo("gordon");
        assertThat(out.dividendPerShare()).isEqualTo(2.0);
        assertThat(out.result().intrinsicValue()).isCloseTo(41.2, within(1e-9));
        assertThat(out.result().upside()).isCloseTo((41.2 - 80.0) / 80.0, within(1e-9));
    }

    @Test
    void ddmTwoStageWithAnExplicitDividend() {
        DdmOutcome out = service.ddm(new DdmCommand("AAPL", 1.0, 0.10, 0.02, 2, 0.10));

        assertThat(out.model()).isEqualTo("two-stage");
        assertThat(out.result().intrinsicValue()).isCloseTo(14.75, within(1e-9));
    }

    @Test
    void ddmDoesNotApplyToANonPayer() {
        data.quotes.put("NVDA", new Quote("NVDA", new BigDecimal("100"), null, BigDecimal.ZERO));

        assertThatThrownBy(() -> service.ddm(new DdmCommand("NVDA", null, 0.08, 0.03, null, null)))
                .isInstanceOf(ValuationNotApplicableException.class)
                .hasMessageContaining("NVDA");
    }

    // ---- Lynch

    @Test
    void lynchPullsEpsAndGrowthFromFundamentals() {
        data.fundamentals.put("AAPL", new Fundamentals(null, null, new BigDecimal("5.0"), new BigDecimal("0.20")));
        data.quotes.put("AAPL", new Quote("AAPL", new BigDecimal("80"), null, BigDecimal.ZERO));

        LynchOutcome out = service.lynch(new LynchCommand("AAPL", null, null, null));

        assertThat(out.result().fairValue()).isCloseTo(100.0, within(1e-9));
        assertThat(out.result().peg()).isCloseTo(0.8, within(1e-9));
    }

    @Test
    void lynchRejectsNonPositiveEpsOrGrowth() {
        assertThatThrownBy(() -> service.lynch(new LynchCommand("AAPL", -1.0, 0.2, null)))
                .isInstanceOf(ValuationNotApplicableException.class).hasMessageContaining("EPS");
        assertThatThrownBy(() -> service.lynch(new LynchCommand("AAPL", 5.0, 0.0, null)))
                .isInstanceOf(ValuationNotApplicableException.class).hasMessageContaining("Growth");
    }

    // ---- Peer analysis and compare

    private void sixTechPeersWithPe(String subjectPe) {
        data.profiles.put("AAPL", new CompanyProfile("AAPL", "Technology", "Consumer Electronics", "Apple Inc."));
        String[] pe = {"10", "12", "14", "16", "18", "20"};
        for (int i = 0; i < pe.length; i++) {
            String symbol = "P" + i;
            data.peers.add(new Peer(symbol, "Peer " + i));
            data.metric(symbol, ValuationMetric.PE, pe[i]);
        }
        data.metric("AAPL", ValuationMetric.PE, subjectPe);
    }

    @Test
    void analyzePlacesTheSubjectAmongItsPeers() {
        sixTechPeersWithPe("9");

        PeerOutcome out = service.analyze(new PeerCommand("AAPL", ValuationMetric.PE));

        assertThat(out.sector()).isEqualTo("Technology");
        assertThat(out.value()).isEqualTo(9.0);
        assertThat(out.quartiles().q1()).isCloseTo(12.5, within(1e-9));
        assertThat(out.quartiles().median()).isCloseTo(15.0, within(1e-9));
        assertThat(out.quartiles().q3()).isCloseTo(17.5, within(1e-9));
        assertThat(out.signal()).isEqualTo(ValuationSignal.UNDERVALUED);
    }

    @Test
    void analyzeNeedsAtLeastFourPeersWithData() {
        data.profiles.put("AAPL", new CompanyProfile("AAPL", "Technology", "x", "Apple"));
        data.peers.addAll(List.of(new Peer("A", "A"), new Peer("B", "B"), new Peer("C", "C")));
        for (String s : new String[] {"A", "B", "C"}) data.metric(s, ValuationMetric.PE, "10");
        data.metric("AAPL", ValuationMetric.PE, "9");

        assertThatThrownBy(() -> service.analyze(new PeerCommand("AAPL", ValuationMetric.PE)))
                .isInstanceOf(InsufficientPeerDataException.class);
    }

    @Test
    void analyzeOfATickerWithoutASectorIsNotFound() {
        assertThatThrownBy(() -> service.analyze(new PeerCommand("ZZZ", ValuationMetric.PE)))
                .isInstanceOf(TickerNotFoundException.class);
    }

    @Test
    void analyzeWhenTheSubjectHasNoMetricIsNotApplicable() {
        sixTechPeersWithPe("9");
        assertThatThrownBy(() -> service.analyze(new PeerCommand("AAPL", ValuationMetric.PB)))
                .isInstanceOf(InsufficientPeerDataException.class); // peers have no P/B either

        data.metric("P0", ValuationMetric.PB, "1").metric("P1", ValuationMetric.PB, "2")
            .metric("P2", ValuationMetric.PB, "3").metric("P3", ValuationMetric.PB, "4");
        assertThatThrownBy(() -> service.analyze(new PeerCommand("AAPL", ValuationMetric.PB)))
                .isInstanceOf(ValuationNotApplicableException.class)
                .hasMessageContaining("PB");
    }

    @Test
    void compareCombinesThePeerSignalWithTheDcfUpside() {
        sixTechPeersWithPe("9"); // UNDERVALUED
        DcfCommand dcf = new DcfCommand("AAPL", 100.0, 10.0, null, 2, List.of(new GrowthStage(2, 0.0)), 0.10, 0.0); // upside +25%

        CompareOutcome out = service.compare(new CompareCommand(new PeerCommand("AAPL", ValuationMetric.PE), dcf));

        assertThat(out.verdict()).isEqualTo(Verdict.STRONG_BUY);
        assertThat(out.price()).isEqualTo(80.0);
        assertThat(out.dcf().intrinsicValue()).isCloseTo(100.0, within(1e-9));
        assertThat(out.peer().signal()).isEqualTo(ValuationSignal.UNDERVALUED);
    }
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && mvn -B -pl valuation -am test -Dtest=ValuationServiceTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL, compilation errors "cannot find symbol: class ValuationService / DcfCommand ...".

- [ ] **Step 3: Write the implementation**

All files are in `backend/valuation/src/main/java/com/finrisk/valuation/application/`.

`TickerNotFoundException.java`:

```java
package com.finrisk.valuation.application;

public class TickerNotFoundException extends RuntimeException {

    public TickerNotFoundException(String ticker) {
        super("No market data found for ticker " + ticker);
    }
}
```

`ValuationNotApplicableException.java`:

```java
package com.finrisk.valuation.application;

/** The ticker exists but this model cannot value it (no dividend, negative cash flow, missing metric). */
public class ValuationNotApplicableException extends RuntimeException {

    public ValuationNotApplicableException(String message) {
        super(message);
    }
}
```

`DcfCommand.java`:

```java
package com.finrisk.valuation.application;

import com.finrisk.valuation.domain.GrowthStage;

import java.util.List;

/**
 * {@code stages} wins when given; otherwise one stage of {@code projectionYears} at {@code growthRate}
 * (default 0). {@code fcf} and {@code sharesOutstanding} are looked up when null.
 */
public record DcfCommand(
        String ticker,
        Double fcf,
        Double sharesOutstanding,
        Double growthRate,
        int projectionYears,
        List<GrowthStage> stages,
        double discountRate,
        double terminalGrowthRate) {}
```

`DdmCommand.java`:

```java
package com.finrisk.valuation.application;

public record DdmCommand(
        String ticker,
        Double dividendPerShare,
        double discountRate,
        double terminalGrowthRate,
        Integer highGrowthYears,
        Double highGrowthRate) {}
```

`LynchCommand.java`:

```java
package com.finrisk.valuation.application;

public record LynchCommand(String ticker, Double eps, Double growthRate, Double dividendPerShare) {}
```

`PeerCommand.java`:

```java
package com.finrisk.valuation.application;

import com.finrisk.marketdata.ValuationMetric;

public record PeerCommand(String ticker, ValuationMetric metric) {}
```

`CompareCommand.java`:

```java
package com.finrisk.valuation.application;

public record CompareCommand(PeerCommand peer, DcfCommand dcf) {}
```

`DcfOutcome.java`:

```java
package com.finrisk.valuation.application;

import com.finrisk.valuation.domain.DcfResult;

public record DcfOutcome(String ticker, Double price, DcfResult result) {}
```

`DdmOutcome.java`:

```java
package com.finrisk.valuation.application;

import com.finrisk.valuation.domain.DdmResult;

/** {@code model} is "gordon" or "two-stage". */
public record DdmOutcome(String ticker, Double price, double dividendPerShare, String model, DdmResult result) {}
```

`LynchOutcome.java`:

```java
package com.finrisk.valuation.application;

import com.finrisk.valuation.domain.LynchResult;

public record LynchOutcome(String ticker, Double price, double eps, double growthRate, LynchResult result) {}
```

`PeerOutcome.java`:

```java
package com.finrisk.valuation.application;

import com.finrisk.marketdata.ValuationMetric;
import com.finrisk.valuation.domain.PeerStats;
import com.finrisk.valuation.domain.ValuationSignal;

public record PeerOutcome(
        String ticker,
        String sector,
        ValuationMetric metric,
        double value,
        PeerStats.Quartiles quartiles,
        ValuationSignal signal) {}
```

`CompareOutcome.java`:

```java
package com.finrisk.valuation.application;

import com.finrisk.valuation.domain.DcfResult;
import com.finrisk.valuation.domain.Verdict;

public record CompareOutcome(PeerOutcome peer, Double price, DcfResult dcf, Verdict verdict) {}
```

`ValuationService.java`:

```java
package com.finrisk.valuation.application;

import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.MarketData;
import com.finrisk.marketdata.Peer;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;
import com.finrisk.valuation.domain.DcfInput;
import com.finrisk.valuation.domain.DcfModel;
import com.finrisk.valuation.domain.DcfResult;
import com.finrisk.valuation.domain.DdmInput;
import com.finrisk.valuation.domain.DdmModel;
import com.finrisk.valuation.domain.GrowthStage;
import com.finrisk.valuation.domain.LynchInput;
import com.finrisk.valuation.domain.LynchModel;
import com.finrisk.valuation.domain.PeerStats;
import com.finrisk.valuation.domain.Rates;
import com.finrisk.valuation.domain.Verdict;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

/** Valuation use cases. Talks to market data only through the MarketData port. */
@Service
public class ValuationService {

    private static final int PEER_LIMIT = 50;

    private final MarketData marketData;

    public ValuationService(MarketData marketData) {
        this.marketData = marketData;
    }

    public DcfOutcome dcf(DcfCommand c) {
        Rates.requireDiscountAboveTerminal(c.discountRate(), c.terminalGrowthRate());
        Quote quote = requireQuote(c.ticker());

        Double fcf = c.fcf();
        Double shares = c.sharesOutstanding();
        if (fcf == null || shares == null) {
            Fundamentals f = marketData.fetchFundamentals(c.ticker()).orElseThrow(() ->
                    new ValuationNotApplicableException("Free cash flow data unavailable for " + c.ticker()));
            if (fcf == null) fcf = number(f.freeCashFlow());
            if (shares == null) shares = number(f.sharesOutstanding());
        }
        if (shares == null) shares = number(quote.sharesOutstanding());
        if (fcf == null || shares == null || fcf <= 0 || shares <= 0) {
            throw new ValuationNotApplicableException(
                    "DCF needs a positive free cash flow and share count for " + c.ticker());
        }

        List<GrowthStage> stages = c.stages() != null && !c.stages().isEmpty()
                ? c.stages()
                : List.of(new GrowthStage(c.projectionYears(), c.growthRate() == null ? 0.0 : c.growthRate()));
        Double price = number(quote.price());
        DcfResult result = DcfModel.compute(new DcfInput(
                fcf, shares, stages, c.discountRate(), c.terminalGrowthRate(), price));
        return new DcfOutcome(c.ticker(), price, result);
    }

    public DdmOutcome ddm(DdmCommand c) {
        Rates.requireDiscountAboveTerminal(c.discountRate(), c.terminalGrowthRate());
        Quote quote = requireQuote(c.ticker());

        Double dividend = c.dividendPerShare() != null ? c.dividendPerShare() : number(quote.lastDividend());
        if (dividend == null || dividend <= 0) {
            throw new ValuationNotApplicableException(
                    "No dividend available for " + c.ticker() + "; DDM does not apply");
        }
        Double price = number(quote.price());
        var result = DdmModel.compute(new DdmInput(
                dividend, c.discountRate(), c.terminalGrowthRate(), c.highGrowthYears(), c.highGrowthRate(), price));
        return new DdmOutcome(c.ticker(), price, dividend,
                c.highGrowthYears() != null ? "two-stage" : "gordon", result);
    }

    public LynchOutcome lynch(LynchCommand c) {
        Quote quote = requireQuote(c.ticker());

        Double eps = c.eps();
        Double growth = c.growthRate();
        if (eps == null || growth == null) {
            Fundamentals f = marketData.fetchFundamentals(c.ticker()).orElseThrow(() ->
                    new ValuationNotApplicableException("EPS data unavailable for " + c.ticker()));
            if (eps == null) eps = number(f.eps());
            if (growth == null) growth = number(f.epsGrowth());
        }
        if (eps == null || !(eps > 0)) {
            throw new ValuationNotApplicableException("EPS must be positive for Lynch fair value");
        }
        if (growth == null || !(growth > 0)) {
            throw new ValuationNotApplicableException("Growth rate must be positive for Lynch fair value");
        }

        Double price = number(quote.price());
        double dividend = c.dividendPerShare() != null ? c.dividendPerShare()
                : quote.lastDividend() != null ? quote.lastDividend().doubleValue() : 0.0;
        double dividendYield = price != null && price > 0 ? dividend / price : 0.0;
        var result = LynchModel.compute(new LynchInput(eps, growth, price, dividendYield));
        return new LynchOutcome(c.ticker(), price, eps, growth, result);
    }

    public PeerOutcome analyze(PeerCommand c) {
        CompanyProfile profile = marketData.fetchProfile(c.ticker());
        if ("Unknown".equals(profile.sector())) {
            throw new TickerNotFoundException(c.ticker());
        }
        PeerStats stats = PeerStats.of(peerMetrics(profile.sector(), c.metric()));
        double value = marketData.fetchMetric(c.ticker(), c.metric()).map(BigDecimal::doubleValue).orElseThrow(() ->
                new ValuationNotApplicableException("Metric " + c.metric() + " not available for " + c.ticker()));
        return new PeerOutcome(c.ticker(), profile.sector(), c.metric(), value, stats.quartiles(), stats.signal(value));
    }

    public CompareOutcome compare(CompareCommand c) {
        PeerOutcome peer = analyze(c.peer());
        DcfOutcome dcf = dcf(c.dcf());
        return new CompareOutcome(peer, dcf.price(), dcf.result(), Verdict.of(peer.signal(), dcf.result().upside()));
    }

    private Quote requireQuote(String ticker) {
        return marketData.fetchQuote(ticker).orElseThrow(() -> new TickerNotFoundException(ticker));
    }

    /** One metric lookup per peer, in parallel on virtual threads. A peer that fails or has no value counts as null. */
    private List<Double> peerMetrics(String sector, ValuationMetric metric) {
        List<Peer> peers = marketData.fetchPeers(sector, PEER_LIMIT);
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<Double>> futures = peers.stream()
                    .map(p -> executor.submit(() ->
                            marketData.fetchMetric(p.symbol(), metric).map(BigDecimal::doubleValue).orElse(null)))
                    .toList();
            List<Double> values = new ArrayList<>();
            for (Future<Double> future : futures) {
                try {
                    values.add(future.get());
                } catch (ExecutionException e) {
                    values.add(null);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new IllegalStateException("Interrupted while loading peer data", e);
                }
            }
            return values;
        }
    }

    private static Double number(BigDecimal value) {
        return value == null ? null : value.doubleValue();
    }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && mvn -B -pl valuation -am test`
Expected: `ValuationServiceTest` `Tests run: 17`, all earlier tests green, `BUILD SUCCESS`.

- [ ] **Step 5: Commit**

```bash
git add backend/valuation
git commit -m "feat(valuation): ValuationService use cases over the MarketData port"
```

---

### Task 7: Valuation REST API

**Files:**
- Create: `backend/valuation/src/main/java/com/finrisk/valuation/web/{StageRequest,DcfRequest,DdmRequest,LynchRequest,AnalyzeRequest,CompareRequest,ValuationController,ValuationExceptionHandler}.java`
- Test: `backend/valuation/src/test/java/com/finrisk/valuation/web/ValuationControllerTest.java`

**Interfaces:**
- Consumes: `ValuationService`, commands and outcomes (Task 6); `FakeMarketData` (Task 6).
- Produces: endpoints `POST /api/v1/valuation/{dcf,ddm,lynch,analyze,compare}`; error body `ValuationExceptionHandler.ApiError(String code, String message, Map<String,Object> details)` with codes `VALIDATION_ERROR` (400), `TICKER_NOT_FOUND` (404), `NOT_APPLICABLE` (422).

- [ ] **Step 1: Write the failing controller tests** (standalone MockMvc: no Spring context needed)

`backend/valuation/src/test/java/com/finrisk/valuation/web/ValuationControllerTest.java`:

```java
package com.finrisk.valuation.web;

import com.finrisk.marketdata.Quote;
import com.finrisk.valuation.application.ValuationService;
import com.finrisk.valuation.support.FakeMarketData;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;

import static org.hamcrest.Matchers.closeTo;
import static org.hamcrest.Matchers.hasItem;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ValuationControllerTest {

    private final FakeMarketData data = new FakeMarketData();
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        data.quotes.put("AAPL", new Quote("AAPL", new BigDecimal("80"), new BigDecimal("10"), new BigDecimal("2.0")));
        data.quotes.put("NVDA", new Quote("NVDA", new BigDecimal("100"), null, BigDecimal.ZERO));
        mvc = MockMvcBuilders
                .standaloneSetup(new ValuationController(new ValuationService(data)))
                .setControllerAdvice(new ValuationExceptionHandler())
                .build();
    }

    private ResultActions postJson(String path, String json) throws Exception {
        return mvc.perform(post("/api/v1/valuation/" + path).contentType(MediaType.APPLICATION_JSON).content(json));
    }

    @Test
    void dcfReturnsTheComputedValuation() throws Exception {
        postJson("dcf", """
                {"ticker":"aapl","fcf":100,"sharesOutstanding":10,"projectionYears":2,"growthRate":0,
                 "discountRate":0.10,"terminalGrowthRate":0}""")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ticker").value("AAPL"))
                .andExpect(jsonPath("$.price").value(80.0))
                .andExpect(jsonPath("$.result.intrinsicValue").value(closeTo(100.0, 1e-9)))
                .andExpect(jsonPath("$.result.upside").value(closeTo(0.25, 1e-9)));
    }

    @Test
    void ddmReturnsTheModelUsed() throws Exception {
        postJson("ddm", """
                {"ticker":"AAPL","discountRate":0.08,"terminalGrowthRate":0.03}""")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.model").value("gordon"))
                .andExpect(jsonPath("$.result.intrinsicValue").value(closeTo(41.2, 1e-9)));
    }

    @Test
    void aDiscountRateThatIsNotAboveTerminalGrowthIsABadRequest() throws Exception {
        postJson("dcf", """
                {"ticker":"AAPL","fcf":100,"sharesOutstanding":10,"discountRate":0.02,"terminalGrowthRate":0.03}""")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"))
                .andExpect(jsonPath("$.message").value("discountRate must be greater than terminalGrowthRate"));
    }

    @Test
    void beanValidationFailuresListTheOffendingFields() throws Exception {
        postJson("dcf", """
                {"ticker":"AA PL","discountRate":-1,"terminalGrowthRate":0}""")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"))
                .andExpect(jsonPath("$.details.fields[*].field").value(hasItem("ticker")))
                .andExpect(jsonPath("$.details.fields[*].field").value(hasItem("discountRate")));
    }

    @Test
    void malformedJsonAndUnknownMetricsAreBadRequests() throws Exception {
        postJson("dcf", "{not json").andExpect(status().isBadRequest());
        postJson("analyze", """
                {"ticker":"AAPL","metric":"roe"}""")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("roe")));
    }

    @Test
    void anUnknownTickerIs404() throws Exception {
        postJson("dcf", """
                {"ticker":"ZZZ","fcf":100,"sharesOutstanding":10,"discountRate":0.10,"terminalGrowthRate":0}""")
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("TICKER_NOT_FOUND"));
    }

    @Test
    void aModelThatDoesNotApplyIs422() throws Exception {
        postJson("ddm", """
                {"ticker":"NVDA","discountRate":0.08,"terminalGrowthRate":0.03}""")
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("NOT_APPLICABLE"));
    }
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && mvn -B -pl valuation -am test -Dtest=ValuationControllerTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL, compilation errors "cannot find symbol: class ValuationController / ValuationExceptionHandler".

- [ ] **Step 3: Write the web layer**

All files are in `backend/valuation/src/main/java/com/finrisk/valuation/web/`.

`StageRequest.java`:

```java
package com.finrisk.valuation.web;

import com.finrisk.valuation.domain.GrowthStage;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Positive;

public record StageRequest(@Positive @Max(100) int years, double rate) {

    GrowthStage toDomain() {
        return new GrowthStage(years, rate);
    }
}
```

`DcfRequest.java`:

```java
package com.finrisk.valuation.web;

import com.finrisk.valuation.application.DcfCommand;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.Locale;

public record DcfRequest(
        @NotBlank @Pattern(regexp = DcfRequest.TICKER) String ticker,
        Double fcf,
        @Positive Double sharesOutstanding,
        Double growthRate,
        @Positive @Max(100) Integer projectionYears,
        @Valid @Size(min = 1, max = 20) List<StageRequest> stages,
        @NotNull @Positive Double discountRate,
        @NotNull Double terminalGrowthRate) {

    static final String TICKER = "^[A-Za-z0-9.\\-]{1,10}$";

    DcfCommand toCommand() {
        return new DcfCommand(
                ticker.toUpperCase(Locale.ROOT),
                fcf,
                sharesOutstanding,
                growthRate,
                projectionYears == null ? 10 : projectionYears,
                stages == null ? null : stages.stream().map(StageRequest::toDomain).toList(),
                discountRate,
                terminalGrowthRate);
    }
}
```

`DdmRequest.java`:

```java
package com.finrisk.valuation.web;

import com.finrisk.valuation.application.DdmCommand;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;

import java.util.Locale;

public record DdmRequest(
        @NotBlank @Pattern(regexp = DcfRequest.TICKER) String ticker,
        @Positive Double dividendPerShare,
        @NotNull @Positive Double discountRate,
        @NotNull Double terminalGrowthRate,
        @Positive @Max(100) Integer highGrowthYears,
        Double highGrowthRate) {

    DdmCommand toCommand() {
        return new DdmCommand(ticker.toUpperCase(Locale.ROOT), dividendPerShare, discountRate,
                terminalGrowthRate, highGrowthYears, highGrowthRate);
    }
}
```

`LynchRequest.java`:

```java
package com.finrisk.valuation.web;

import com.finrisk.valuation.application.LynchCommand;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.PositiveOrZero;

import java.util.Locale;

public record LynchRequest(
        @NotBlank @Pattern(regexp = DcfRequest.TICKER) String ticker,
        Double eps,
        Double growthRate,
        @PositiveOrZero Double dividendPerShare) {

    LynchCommand toCommand() {
        return new LynchCommand(ticker.toUpperCase(Locale.ROOT), eps, growthRate, dividendPerShare);
    }
}
```

`AnalyzeRequest.java`:

```java
package com.finrisk.valuation.web;

import com.finrisk.marketdata.ValuationMetric;
import com.finrisk.valuation.application.PeerCommand;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

import java.util.Locale;

public record AnalyzeRequest(
        @NotBlank @Pattern(regexp = DcfRequest.TICKER) String ticker,
        @NotBlank String metric) {

    PeerCommand toCommand() {
        return new PeerCommand(ticker.toUpperCase(Locale.ROOT), ValuationMetric.parse(metric));
    }
}
```

`CompareRequest.java`:

```java
package com.finrisk.valuation.web;

import com.finrisk.marketdata.ValuationMetric;
import com.finrisk.valuation.application.CompareCommand;
import com.finrisk.valuation.application.DcfCommand;
import com.finrisk.valuation.application.PeerCommand;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.Locale;

public record CompareRequest(
        @NotBlank @Pattern(regexp = DcfRequest.TICKER) String ticker,
        @NotBlank String metric,
        Double fcf,
        @Positive Double sharesOutstanding,
        Double growthRate,
        @Positive @Max(100) Integer projectionYears,
        @Valid @Size(min = 1, max = 20) List<StageRequest> stages,
        @NotNull @Positive Double discountRate,
        @NotNull Double terminalGrowthRate) {

    CompareCommand toCommand() {
        String symbol = ticker.toUpperCase(Locale.ROOT);
        DcfCommand dcf = new DcfRequest(symbol, fcf, sharesOutstanding, growthRate, projectionYears, stages,
                discountRate, terminalGrowthRate).toCommand();
        return new CompareCommand(new PeerCommand(symbol, ValuationMetric.parse(metric)), dcf);
    }
}
```

`ValuationController.java`:

```java
package com.finrisk.valuation.web;

import com.finrisk.valuation.application.CompareOutcome;
import com.finrisk.valuation.application.DcfOutcome;
import com.finrisk.valuation.application.DdmOutcome;
import com.finrisk.valuation.application.LynchOutcome;
import com.finrisk.valuation.application.PeerOutcome;
import com.finrisk.valuation.application.ValuationService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/valuation")
public class ValuationController {

    private final ValuationService service;

    public ValuationController(ValuationService service) {
        this.service = service;
    }

    @PostMapping("/dcf")
    public DcfOutcome dcf(@Valid @RequestBody DcfRequest request) {
        return service.dcf(request.toCommand());
    }

    @PostMapping("/ddm")
    public DdmOutcome ddm(@Valid @RequestBody DdmRequest request) {
        return service.ddm(request.toCommand());
    }

    @PostMapping("/lynch")
    public LynchOutcome lynch(@Valid @RequestBody LynchRequest request) {
        return service.lynch(request.toCommand());
    }

    @PostMapping("/analyze")
    public PeerOutcome analyze(@Valid @RequestBody AnalyzeRequest request) {
        return service.analyze(request.toCommand());
    }

    @PostMapping("/compare")
    public CompareOutcome compare(@Valid @RequestBody CompareRequest request) {
        return service.compare(request.toCommand());
    }
}
```

`ValuationExceptionHandler.java`:

```java
package com.finrisk.valuation.web;

import com.finrisk.valuation.application.TickerNotFoundException;
import com.finrisk.valuation.application.ValuationNotApplicableException;
import com.finrisk.valuation.domain.InsufficientPeerDataException;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.List;
import java.util.Map;

/** Valuation's own error mapping. Highest precedence so the generic handlers in other modules do not take over. */
@RestControllerAdvice(assignableTypes = ValuationController.class)
@Order(Ordered.HIGHEST_PRECEDENCE)
public class ValuationExceptionHandler {

    public record ApiError(String code, String message, Map<String, Object> details) {}

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ApiError> invalidFields(MethodArgumentNotValidException ex) {
        List<Map<String, String>> fields = ex.getBindingResult().getFieldErrors().stream()
                .map(e -> Map.of("field", e.getField(), "message", e.getDefaultMessage() == null ? "" : e.getDefaultMessage()))
                .toList();
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(new ApiError("VALIDATION_ERROR", "Validation failed", Map.of("fields", fields)));
    }

    @ExceptionHandler({IllegalArgumentException.class, HttpMessageNotReadableException.class})
    ResponseEntity<ApiError> badRequest(Exception ex) {
        String message = ex instanceof HttpMessageNotReadableException ? "Malformed JSON request body" : ex.getMessage();
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(new ApiError("VALIDATION_ERROR", message, Map.of()));
    }

    @ExceptionHandler(TickerNotFoundException.class)
    ResponseEntity<ApiError> tickerNotFound(TickerNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(new ApiError("TICKER_NOT_FOUND", ex.getMessage(), Map.of()));
    }

    @ExceptionHandler({ValuationNotApplicableException.class, InsufficientPeerDataException.class})
    ResponseEntity<ApiError> notApplicable(RuntimeException ex) {
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY)
                .body(new ApiError("NOT_APPLICABLE", ex.getMessage(), Map.of()));
    }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && mvn -B -pl valuation -am test`
Expected: `ValuationControllerTest` `Tests run: 7`; whole module green; `BUILD SUCCESS`.

- [ ] **Step 5: Commit**

```bash
git add backend/valuation
git commit -m "feat(valuation): REST API with validation and error mapping"
```

---

## Phase C: Portfolio and Risk on PostgreSQL

### Task 8: Import the risk code into `backend/risk` as the Portfolio and Risk contexts

This task moves code and changes no behaviour. The existing unit tests are the safety net. It uses file copies and a rewrite script because `risk-management-ms` is a separate git repo.

**Files:**
- Modify: `backend/pom.xml` (add `<module>risk</module>`)
- Create: `backend/risk/pom.xml`
- Create (by script): everything under `backend/risk/src/main/java/com/finrisk/{shared,portfolio,risk}/` and `backend/risk/src/test/java/com/finrisk/`
- Create: `backend/risk/src/main/java/com/finrisk/risk/web/RiskController.java` (split out of `PortfolioController`)
- Modify (after copy): `backend/risk/src/main/java/com/finrisk/portfolio/web/PortfolioController.java`
- Create: `backend/risk/src/test/java/com/finrisk/RiskModuleTestApplication.java`

**Interfaces:**
- Consumes: `MarketData`, `PricePoint`, `CompanyProfile`, `EtfHolding` (Task 1; they keep their package `com.finrisk.marketdata`, so imports of those three do not change).
- Produces (package map; later tasks use the new names):

| Old (`com.finrisk.…`) | New |
|---|---|
| `model.*` (incl. `RiskLevel`, `AssetType`, sealed `Asset`/`Transaction`) | `portfolio.domain` |
| `dto.response.{Holding,AssetPricePoint,HoldingProfitLoss}` (read models the repositories return) | `portfolio.domain` |
| `exception.*` (except `DaoException`) | `portfolio.domain.exception` |
| `dao.*Dao` interfaces | `portfolio.domain.repository.*Repository` (same names, `Dao` becomes `Repository`) |
| `dao.impl.*DaoJdbc` | `portfolio.infrastructure.Postgres*Repository` |
| `factory.*` (they build domain objects from request DTOs, so they are application code) | `portfolio.application.factory` |
| `mapper.*` | `portfolio.application.mapper` |
| `service.{Account,Asset,MarketData,Portfolio,ProfitLoss,Transaction,User}Service` | `portfolio.application` |
| `controller.{Account,Asset,Transaction,User}Controller`, `GlobalExceptionHandler` | `portfolio.web` |
| `dto.request.*`, remaining portfolio `dto.response.*` | `portfolio.web.dto` |
| `service.{Risk,Beta,Alpha,Correlation,Drawdown,Downside,Diversification,SectorExposure,EtfLookThrough}Service`, `PortfolioPrices`, `config.StrategyConfig` | `risk.application` |
| `strategy.risk.*`, `util.ReturnsMath` | `risk.domain` |
| risk `dto.response.*` (Alpha, Beta, Correlation, Diversification, Downside, Drawdown, HoldingBeta, HoldingDrawdown, LookThrough, Overlap, RiskBreakdownItem, RiskScore, SectorAllocation, SectorExposure, AssetTypeAllocation) | `risk.web.dto` |
| `dto.response.{Page,ErrorBody}`, `exception.DaoException`, `util.{Db,SqlSort,JdbcSqlExceptionMapper}`, `config.{DatabaseConnection,JacksonConfig}` | `shared` |
| `marketdata.MarketDataProvider` | `marketdata.MarketData` (same methods for the existing three; the FMP class is not copied) |

- [ ] **Step 1: Confirm the source is what the plan assumes**

Run:

```bash
cd "$(git rev-parse --show-toplevel)"
git -C risk-management-ms branch --show-current
git -C risk-management-ms status --short | grep -v 'target/' || true
```

Expected: the branch is `feature/portfolio-analytics-extras`, and the only non-`target/` change is `openapi.yaml` (it is not copied). If the branch differs, stop: the analytics endpoints (alpha, drawdown, ETF look-through ...) live on that branch.

- [ ] **Step 2: Add the module and its POM**

In `backend/pom.xml` set:

```xml
  <modules>
    <module>marketdata-api</module>
    <module>marketdata</module>
    <module>valuation</module>
    <module>risk</module>
  </modules>
```

`backend/risk/pom.xml`:

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
  <artifactId>risk</artifactId>
  <description>Portfolio context (users, accounts, assets, trades) and Risk context (analytics). Sees market data only through MarketData.</description>

  <dependencies>
    <dependency>
      <groupId>com.finrisk</groupId>
      <artifactId>marketdata-api</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-jdbc</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 3: Copy and restructure the sources**

Save this as `backend/restructure-risk.sh`, run it once from the repo root, then delete it (it is a one-off):

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

S=risk-management-ms/src
SM=$S/main/java/com/finrisk
ST=$S/test/java/com/finrisk
D=backend/risk/src
DM=$D/main/java/com/finrisk
DT=$D/test/java/com/finrisk

mkdir -p "$DM"/shared \
         "$DM"/portfolio/{domain/{exception,repository},application/{mapper,factory},infrastructure,web/dto} \
         "$DM"/risk/{domain,application,web/dto} \
         "$DT"/portfolio/{application/mapper,web} "$DT"/risk/{application,domain}

# shared kernel
cp "$SM"/dto/response/{Page,ErrorBody}.java "$SM"/exception/DaoException.java \
   "$SM"/util/{Db,SqlSort,JdbcSqlExceptionMapper}.java "$SM"/config/{DatabaseConnection,JacksonConfig}.java "$DM"/shared/

# portfolio: domain
cp "$SM"/model/*.java "$SM"/dto/response/{Holding,AssetPricePoint,HoldingProfitLoss}.java "$DM"/portfolio/domain/
cp $(ls "$SM"/exception/*.java | grep -v DaoException) "$DM"/portfolio/domain/exception/
cp "$SM"/dao/*.java "$DM"/portfolio/domain/repository/
for f in "$DM"/portfolio/domain/repository/*Dao.java; do mv "$f" "${f%Dao.java}Repository.java"; done
for f in "$SM"/dao/impl/*.java; do
  b=$(basename "$f" .java)
  cp "$f" "$DM/portfolio/infrastructure/Postgres${b%DaoJdbc}Repository.java"
done

# portfolio: application and web
cp "$SM"/mapper/*.java "$DM"/portfolio/application/mapper/
cp "$SM"/factory/*.java "$DM"/portfolio/application/factory/
for s in Account Asset MarketData Portfolio ProfitLoss Transaction User; do cp "$SM/service/${s}Service.java" "$DM"/portfolio/application/; done
cp "$SM"/dto/request/*.java "$DM"/portfolio/web/dto/
for r in Account Asset Bond Crypto Etf Stock Transaction User Portfolio ProfitLoss; do cp "$SM/dto/response/${r}Response.java" "$DM"/portfolio/web/dto/; done
cp "$SM"/controller/{Account,Asset,Transaction,User}Controller.java "$SM"/controller/{GlobalExceptionHandler,PortfolioController}.java "$DM"/portfolio/web/

# risk
for r in AlphaResponse BetaResponse CorrelationResponse DiversificationResponse DownsideResponse DrawdownResponse \
         HoldingBeta HoldingDrawdown LookThroughResponse OverlapResponse RiskBreakdownItem RiskScoreResponse \
         SectorAllocation SectorExposureResponse AssetTypeAllocation; do
  cp "$SM/dto/response/$r.java" "$DM"/risk/web/dto/
done
for s in Risk Beta Alpha Correlation Drawdown Downside Diversification SectorExposure EtfLookThrough; do cp "$SM/service/${s}Service.java" "$DM"/risk/application/; done
cp "$SM"/service/PortfolioPrices.java "$SM"/config/StrategyConfig.java "$DM"/risk/application/
cp "$SM"/strategy/risk/*.java "$SM"/util/ReturnsMath.java "$DM"/risk/domain/

# tests that need no database (the *IT classes are rebuilt on Testcontainers in Task 9; the FMP test moved to Task 2)
for t in Alpha Beta Correlation Diversification Downside Drawdown SectorExposure EtfLookThrough; do cp "$ST/service/${t}ServiceTest.java" "$DT"/risk/application/; done
cp "$ST"/service/PortfolioPricesTest.java "$DT"/risk/application/
cp "$ST"/service/{MarketDataServiceTest,UserServiceTest}.java "$DT"/portfolio/application/
cp "$ST"/mapper/UserMapperTest.java "$DT"/portfolio/application/mapper/
cp "$ST"/controller/UserControllerTest.java "$DT"/portfolio/web/
cp "$ST"/strategy/risk/VolatilityRiskStrategyTest.java "$ST"/util/ReturnsMathTest.java "$DT"/risk/domain/

# 1) every file's package line comes from where the file now lives
find backend/risk/src -name '*.java' | while read -r f; do
  pkg=$(dirname "$f" | sed -E 's|.*/java/||; s|/|.|g')
  perl -0pi -e "s/^package [^;]+;/package $pkg;/m" "$f"
done

# 2) every reference follows the package map
cat > /tmp/finrisk-rewrite.pl <<'PERL'
s/\bcom\.finrisk\.dto\.response\.(Page|ErrorBody)\b/com.finrisk.shared.$1/g;
s/\bcom\.finrisk\.exception\.DaoException\b/com.finrisk.shared.DaoException/g;
s/\bcom\.finrisk\.util\.(Db|SqlSort|JdbcSqlExceptionMapper)\b/com.finrisk.shared.$1/g;
s/\bcom\.finrisk\.config\.(DatabaseConnection|JacksonConfig)\b/com.finrisk.shared.$1/g;
s/\bcom\.finrisk\.dto\.response\.(Holding|AssetPricePoint|HoldingProfitLoss)\b/com.finrisk.portfolio.domain.$1/g;
s/\bcom\.finrisk\.dto\.response\.(AlphaResponse|BetaResponse|CorrelationResponse|DiversificationResponse|DownsideResponse|DrawdownResponse|HoldingBeta|HoldingDrawdown|LookThroughResponse|OverlapResponse|RiskBreakdownItem|RiskScoreResponse|SectorAllocation|SectorExposureResponse|AssetTypeAllocation)\b/com.finrisk.risk.web.dto.$1/g;
s/\bcom\.finrisk\.dto\.response\b/com.finrisk.portfolio.web.dto/g;
s/\bcom\.finrisk\.dto\.request\b/com.finrisk.portfolio.web.dto/g;
s/\bcom\.finrisk\.model\b/com.finrisk.portfolio.domain/g;
s/\bcom\.finrisk\.exception\b/com.finrisk.portfolio.domain.exception/g;
s/\bcom\.finrisk\.factory\b/com.finrisk.portfolio.application.factory/g;
s/\bcom\.finrisk\.dao\.impl\b/com.finrisk.portfolio.infrastructure/g;
s/\bcom\.finrisk\.dao\b/com.finrisk.portfolio.domain.repository/g;
s/\bcom\.finrisk\.mapper\b/com.finrisk.portfolio.application.mapper/g;
s/\bcom\.finrisk\.service\.(RiskService|BetaService|AlphaService|CorrelationService|DrawdownService|DownsideService|DiversificationService|SectorExposureService|EtfLookThroughService|PortfolioPrices)\b/com.finrisk.risk.application.$1/g;
s/\bcom\.finrisk\.service\b/com.finrisk.portfolio.application/g;
s/\bcom\.finrisk\.strategy\.risk\b/com.finrisk.risk.domain/g;
s/\bcom\.finrisk\.util\.ReturnsMath\b/com.finrisk.risk.domain.ReturnsMath/g;
s/\bcom\.finrisk\.config\.StrategyConfig\b/com.finrisk.risk.application.StrategyConfig/g;
s/\bcom\.finrisk\.controller\b/com.finrisk.portfolio.web/g;
s/\bMarketDataProvider\b/MarketData/g;
s/\b([A-Za-z]\w*)DaoJdbc\b/Postgres$1Repository/g;
s/\b([A-Za-z]\w*)Dao\b/$1Repository/g;
PERL
find backend/risk/src -name '*.java' -print0 | xargs -0 perl -pi /tmp/finrisk-rewrite.pl
rm /tmp/finrisk-rewrite.pl
echo "restructure done"
```

Run:

```bash
bash backend/restructure-risk.sh && rm backend/restructure-risk.sh
```

Expected: prints `restructure done`.

- [ ] **Step 4: Split `PortfolioController` into a portfolio part and a risk part**

Risk must depend on Portfolio, never the other way round, so the risk endpoints leave `PortfolioController`.

Replace the whole of `backend/risk/src/main/java/com/finrisk/portfolio/web/PortfolioController.java` with:

```java
package com.finrisk.portfolio.web;

import com.finrisk.portfolio.application.PortfolioService;
import com.finrisk.portfolio.application.ProfitLossService;
import com.finrisk.portfolio.web.dto.PortfolioResponse;
import com.finrisk.portfolio.web.dto.ProfitLossResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/accounts/{accountId}")
public class PortfolioController {

    private final PortfolioService portfolioService;
    private final ProfitLossService profitLossService;

    public PortfolioController(PortfolioService portfolioService, ProfitLossService profitLossService) {
        this.portfolioService = portfolioService;
        this.profitLossService = profitLossService;
    }

    @GetMapping("/portfolio")
    public PortfolioResponse portfolio(@PathVariable long accountId) {
        return portfolioService.getPortfolio(accountId);
    }

    @GetMapping("/profit-loss")
    public ProfitLossResponse profitLoss(@PathVariable long accountId) {
        return profitLossService.getProfitLoss(accountId);
    }
}
```

Create `backend/risk/src/main/java/com/finrisk/risk/web/RiskController.java`:

```java
package com.finrisk.risk.web;

import com.finrisk.risk.application.AlphaService;
import com.finrisk.risk.application.BetaService;
import com.finrisk.risk.application.CorrelationService;
import com.finrisk.risk.application.DiversificationService;
import com.finrisk.risk.application.DownsideService;
import com.finrisk.risk.application.DrawdownService;
import com.finrisk.risk.application.EtfLookThroughService;
import com.finrisk.risk.application.RiskService;
import com.finrisk.risk.application.SectorExposureService;
import com.finrisk.risk.web.dto.AlphaResponse;
import com.finrisk.risk.web.dto.BetaResponse;
import com.finrisk.risk.web.dto.CorrelationResponse;
import com.finrisk.risk.web.dto.DiversificationResponse;
import com.finrisk.risk.web.dto.DownsideResponse;
import com.finrisk.risk.web.dto.DrawdownResponse;
import com.finrisk.risk.web.dto.LookThroughResponse;
import com.finrisk.risk.web.dto.OverlapResponse;
import com.finrisk.risk.web.dto.RiskScoreResponse;
import com.finrisk.risk.web.dto.SectorExposureResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/accounts/{accountId}")
public class RiskController {

    private final RiskService riskService;
    private final BetaService betaService;
    private final SectorExposureService sectorExposureService;
    private final DiversificationService diversificationService;
    private final CorrelationService correlationService;
    private final DrawdownService drawdownService;
    private final AlphaService alphaService;
    private final DownsideService downsideService;
    private final EtfLookThroughService etfLookThroughService;

    public RiskController(
            RiskService riskService,
            BetaService betaService,
            SectorExposureService sectorExposureService,
            DiversificationService diversificationService,
            CorrelationService correlationService,
            DrawdownService drawdownService,
            AlphaService alphaService,
            DownsideService downsideService,
            EtfLookThroughService etfLookThroughService) {
        this.riskService = riskService;
        this.betaService = betaService;
        this.sectorExposureService = sectorExposureService;
        this.diversificationService = diversificationService;
        this.correlationService = correlationService;
        this.drawdownService = drawdownService;
        this.alphaService = alphaService;
        this.downsideService = downsideService;
        this.etfLookThroughService = etfLookThroughService;
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

    @GetMapping("/correlation")
    public CorrelationResponse correlation(@PathVariable long accountId) {
        return correlationService.computeCorrelation(accountId);
    }

    @GetMapping("/drawdown")
    public DrawdownResponse drawdown(@PathVariable long accountId) {
        return drawdownService.computeDrawdown(accountId);
    }

    @GetMapping("/alpha")
    public AlphaResponse alpha(
            @PathVariable long accountId, @RequestParam(defaultValue = "0.0") double riskFree) {
        return alphaService.computeAlpha(accountId, riskFree);
    }

    @GetMapping("/downside")
    public DownsideResponse downside(@PathVariable long accountId) {
        return downsideService.computeDownside(accountId);
    }

    @GetMapping("/etf-look-through")
    public LookThroughResponse etfLookThrough(@PathVariable long accountId) {
        return etfLookThroughService.lookThrough(accountId);
    }

    @GetMapping("/etf-overlap")
    public OverlapResponse etfOverlap(@PathVariable long accountId) {
        return etfLookThroughService.overlap(accountId);
    }
}
```

- [ ] **Step 5: Give the module's `@WebMvcTest` a Spring Boot configuration to find**

`backend/risk/src/test/java/com/finrisk/RiskModuleTestApplication.java`:

```java
package com.finrisk;

import org.springframework.boot.autoconfigure.SpringBootApplication;

/** Test-only anchor so @WebMvcTest slices in this module have a configuration class (the real one lives in `app`). */
@SpringBootApplication
public class RiskModuleTestApplication {}
```

- [ ] **Step 6: Compile, then fix what the rewrite could not know**

Run: `cd backend && mvn -B -pl risk -am test-compile`
Expected on the first run: a short list of `cannot find symbol` errors. Fix them as follows, then re-run until it compiles:

1. `portfolio/web/dto/PortfolioResponse.java` used `Holding` from its old package without an import. Add `import com.finrisk.portfolio.domain.Holding;`.
2. `portfolio/web/dto/ProfitLossResponse.java` used `HoldingProfitLoss` the same way. Add `import com.finrisk.portfolio.domain.HoldingProfitLoss;`.
3. For any other error naming a class from the old `dto.response` package, add an import using the package map above.

Then confirm nothing still points at the old layout:

```bash
grep -rnE "com\.finrisk\.(dto|dao|service|controller|model|exception|factory|mapper|strategy|util|config)\b" backend/risk/src || echo "no old package references"
grep -rn "MarketDataProvider\|FmpMarketDataProvider" backend/risk/src || echo "no provider references"
```

Expected: both print the `echo` text.

- [ ] **Step 7: Run the unit tests**

Run: `cd backend && mvn -B -pl risk -am test`
Expected: `risk` module `Tests run: 96, Failures: 0, Errors: 0` (the old module ran 112; the 16 FMP tests now live in `marketdata`), `BUILD SUCCESS`. If a count differs, compare against `cd risk-management-ms && mvn -B -o test` before changing anything.

- [ ] **Step 8: Commit**

```bash
git add backend/pom.xml backend/risk
git commit -m "refactor(risk): import risk-management-ms as portfolio and risk contexts"
```

---

### Task 9: PostgreSQL, atomic cash and trades, Flyway

**Files:**
- Modify: `backend/risk/pom.xml` (PostgreSQL, Flyway, Testcontainers, failsafe)
- Create: `backend/risk/src/main/resources/db/migration/{V1__schema,V2__indexes,V3__views,V4__audit}.sql`
- Create: `backend/risk/src/main/resources/db/dev/V100__dev_seed.sql`
- Modify: `backend/risk/src/main/java/com/finrisk/shared/DatabaseConnection.java` (replace); Create `shared/DataSourceBridge.java`
- Modify: `shared/Db.java` (remove `call`/`bindCall`); Delete: `shared/JdbcSqlExceptionMapper.java`
- Modify (SQL dialect): the seven `portfolio/infrastructure/Postgres*Repository.java` files
- Modify: `portfolio/domain/repository/{AccountRepository,TransactionRepository}.java`, `portfolio/infrastructure/{PostgresAccountRepository,PostgresTransactionRepository}.java`, `portfolio/application/{AccountService,TransactionService}.java`
- Test: `backend/risk/src/test/java/com/finrisk/portfolio/application/AccountServiceTest.java`
- Test: `backend/risk/src/test/java/com/finrisk/support/PostgresTestSupport.java`
- Test: `backend/risk/src/test/java/com/finrisk/portfolio/infrastructure/TradeExecutionIT.java`

**Interfaces:**
- Consumes: the package map from Task 8; `Db.inTx(Function<Connection,T>)`, `Db.findOne(Connection, sql, RowMapper, params...)`, `Db.update(Connection, sql, params...)`, `Db.exec(Connection, ...)`, `Db.insertReturning(Connection, ...)`, `Db.queryLong(Connection, ...)` (all existing).
- Produces:
  - `AccountRepository.adjustCash(long accountId, BigDecimal delta) -> Optional<BigDecimal>`: atomically adds `delta` and returns the new balance; empty when the account does not exist or the balance would go negative. Replaces `updateCashBalance`.
  - `TransactionRepository.executeBuy(long accountId, long assetId, int quantity, BigDecimal unitPrice)` and `executeSell(...)`, replacing `executeBuyProcedure`/`executeSellProcedure`. They throw `AccountNotFoundException`, `AssetNotFoundException`, `InsufficientBalanceException`, `InsufficientQuantityException`.
  - `DatabaseConnection.use(DataSource)` and `DatabaseConnection.getConnection()`.
  - `PostgresTestSupport.dataSource()`: a Flyway-migrated Testcontainers Postgres, shared by integration tests.

- [ ] **Step 1: Dependencies and the failsafe plugin**

In `backend/risk/pom.xml`, add inside `<dependencies>`:

```xml
    <dependency>
      <groupId>org.postgresql</groupId>
      <artifactId>postgresql</artifactId>
      <scope>runtime</scope>
    </dependency>
    <dependency>
      <groupId>org.flywaydb</groupId>
      <artifactId>flyway-core</artifactId>
    </dependency>
    <dependency>
      <groupId>org.flywaydb</groupId>
      <artifactId>flyway-database-postgresql</artifactId>
    </dependency>
    <dependency>
      <groupId>org.testcontainers</groupId>
      <artifactId>postgresql</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.testcontainers</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
```

And add, after `</dependencies>`:

```xml
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-failsafe-plugin</artifactId>
        <configuration>
          <includes>
            <include>**/*IT.java</include>
          </includes>
        </configuration>
        <executions>
          <execution>
            <goals>
              <goal>integration-test</goal>
              <goal>verify</goal>
            </goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
```

(`*IT` classes need Docker for Testcontainers and run on `mvn verify`; `mvn test` skips them.)

- [ ] **Step 2: Write the failing tests**

`backend/risk/src/test/java/com/finrisk/portfolio/application/AccountServiceTest.java` (unit; the race fix starts here):

```java
package com.finrisk.portfolio.application;

import com.finrisk.portfolio.domain.Account;
import com.finrisk.portfolio.domain.exception.AccountNotFoundException;
import com.finrisk.portfolio.domain.exception.InsufficientBalanceException;
import com.finrisk.portfolio.domain.repository.AccountRepository;
import com.finrisk.portfolio.domain.repository.UserRepository;
import com.finrisk.portfolio.web.dto.AccountResponse;
import com.finrisk.portfolio.web.dto.CashMovementRequest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AccountServiceTest {

    private static final Account ACCOUNT =
            new Account(7L, 1L, "Main", new BigDecimal("100.0000"), LocalDateTime.of(2024, 1, 1, 0, 0));

    @Mock AccountRepository accountRepository;
    @Mock UserRepository userRepository;
    @InjectMocks AccountService service;

    @Test
    void depositAddsInOneAtomicStepAndReturnsTheNewBalance() {
        when(accountRepository.findById(7L)).thenReturn(ACCOUNT);
        when(accountRepository.adjustCash(7L, new BigDecimal("25.00"))).thenReturn(Optional.of(new BigDecimal("125.0000")));

        AccountResponse response = service.deposit(7L, new CashMovementRequest(new BigDecimal("25.00")));

        assertThat(response.cashBalance()).isEqualByComparingTo("125");
    }

    @Test
    void withdrawalSubtractsInOneAtomicStep() {
        when(accountRepository.findById(7L)).thenReturn(ACCOUNT);
        when(accountRepository.adjustCash(7L, new BigDecimal("-25.00"))).thenReturn(Optional.of(new BigDecimal("75.0000")));

        AccountResponse response = service.withdraw(7L, new CashMovementRequest(new BigDecimal("25.00")));

        assertThat(response.cashBalance()).isEqualByComparingTo("75");
    }

    @Test
    void aWithdrawalTheBalanceCannotCoverIsRejected() {
        when(accountRepository.findById(7L)).thenReturn(ACCOUNT);
        when(accountRepository.adjustCash(7L, new BigDecimal("-500.00"))).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.withdraw(7L, new CashMovementRequest(new BigDecimal("500.00"))))
                .isInstanceOf(InsufficientBalanceException.class);
    }

    @Test
    void anUnknownAccountIsNotFoundAndNothingIsChanged() {
        when(accountRepository.findById(9L)).thenReturn(null);

        assertThatThrownBy(() -> service.deposit(9L, new CashMovementRequest(BigDecimal.ONE)))
                .isInstanceOf(AccountNotFoundException.class);
        assertThatThrownBy(() -> service.withdraw(9L, new CashMovementRequest(BigDecimal.ONE)))
                .isInstanceOf(AccountNotFoundException.class);
        verify(accountRepository, never()).adjustCash(anyLong(), any());
    }
}
```

`backend/risk/src/test/java/com/finrisk/support/PostgresTestSupport.java`:

```java
package com.finrisk.support;

import com.finrisk.shared.DatabaseConnection;
import com.zaxxer.hikari.HikariDataSource;
import org.flywaydb.core.Flyway;
import org.testcontainers.containers.PostgreSQLContainer;

import javax.sql.DataSource;
import java.util.TimeZone;

/** One Postgres container per test JVM, migrated with the real Flyway files and wired into DatabaseConnection. */
public final class PostgresTestSupport {

    private static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine");
    private static HikariDataSource dataSource;

    private PostgresTestSupport() {}

    public static synchronized DataSource dataSource() {
        if (dataSource == null) {
            TimeZone.setDefault(TimeZone.getTimeZone("UTC"));
            POSTGRES.start();
            dataSource = new HikariDataSource();
            dataSource.setJdbcUrl(POSTGRES.getJdbcUrl());
            dataSource.setUsername(POSTGRES.getUsername());
            dataSource.setPassword(POSTGRES.getPassword());
            dataSource.setMaximumPoolSize(30);
            Flyway.configure().dataSource(dataSource).locations("classpath:db/migration").load().migrate();
            DatabaseConnection.use(dataSource);
        }
        return dataSource;
    }
}
```

`backend/risk/src/test/java/com/finrisk/portfolio/infrastructure/TradeExecutionIT.java`:

```java
package com.finrisk.portfolio.infrastructure;

import com.finrisk.portfolio.domain.exception.InsufficientBalanceException;
import com.finrisk.portfolio.domain.exception.InsufficientQuantityException;
import com.finrisk.shared.Db;
import com.finrisk.support.PostgresTestSupport;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Needs Docker. Runs against a real Postgres, so the locking and the SQL are proven, not assumed. */
class TradeExecutionIT {

    private final PostgresTransactionRepository trades = new PostgresTransactionRepository();
    private final PostgresAccountRepository accounts = new PostgresAccountRepository();
    private long accountId;
    private long assetId;

    @BeforeAll
    static void database() {
        PostgresTestSupport.dataSource();
    }

    @BeforeEach
    void freshAccountAndAsset() {
        long suffix = System.nanoTime();
        long userId = Db.insertReturning(
                "INSERT INTO users (full_name, email) VALUES (?, ?) RETURNING id", rs -> rs.getLong(1),
                "Trader", "trader-" + suffix + "@example.com");
        accountId = Db.insertReturning(
                "INSERT INTO accounts (user_id, account_name, cash_balance) VALUES (?, 'Main', 1000.0000) RETURNING id",
                rs -> rs.getLong(1), userId);
        assetId = Db.insertReturning(
                "INSERT INTO assets (symbol, name, asset_type, current_price, risk_level) VALUES (?, 'Test', 'STOCK', 100.0000, 'MEDIUM') RETURNING id",
                rs -> rs.getLong(1), "T" + (suffix % 1_000_000_000L));
    }

    private BigDecimal cash() {
        return Db.findOne("SELECT cash_balance FROM accounts WHERE id = ?", rs -> rs.getBigDecimal(1), accountId).orElseThrow();
    }

    private long count(String sql, Object... params) {
        return Db.queryLong(sql, params);
    }

    @Test
    void buyMovesCashIntoAPositionAndWritesAnAuditRow() {
        trades.executeBuy(accountId, assetId, 5, new BigDecimal("10.00"));

        assertThat(cash()).isEqualByComparingTo("950");
        assertThat(trades.ownedQuantity(accountId, assetId)).isEqualTo(5);
        assertThat(count("SELECT COUNT(*) FROM audit_logs WHERE action_type = 'BUY_TRANSACTION_CREATED'")).isGreaterThanOrEqualTo(1);
    }

    @Test
    void buyingMoreThanTheBalanceFailsAndChangesNothing() {
        assertThatThrownBy(() -> trades.executeBuy(accountId, assetId, 200, new BigDecimal("10.00")))
                .isInstanceOf(InsufficientBalanceException.class);

        assertThat(cash()).isEqualByComparingTo("1000");
        assertThat(count("SELECT COUNT(*) FROM transactions WHERE account_id = ?", accountId)).isZero();
    }

    @Test
    void sellReturnsTheProceedsAndShrinksThePosition() {
        trades.executeBuy(accountId, assetId, 5, new BigDecimal("10.00"));
        trades.executeSell(accountId, assetId, 2, new BigDecimal("12.00"));

        assertThat(cash()).isEqualByComparingTo("974");
        assertThat(trades.ownedQuantity(accountId, assetId)).isEqualTo(3);
    }

    @Test
    void sellingMoreThanIsOwnedFails() {
        trades.executeBuy(accountId, assetId, 1, new BigDecimal("10.00"));

        assertThatThrownBy(() -> trades.executeSell(accountId, assetId, 2, new BigDecimal("10.00")))
                .isInstanceOf(InsufficientQuantityException.class);
        assertThat(trades.ownedQuantity(accountId, assetId)).isEqualTo(1);
    }

    @Test
    void concurrentBuysNeverOverspendTheAccount() throws Exception {
        // 20 buyers race for a balance that covers exactly 10 purchases of 100.
        List<Callable<Boolean>> buyers = new ArrayList<>();
        for (int i = 0; i < 20; i++) {
            buyers.add(() -> {
                try {
                    trades.executeBuy(accountId, assetId, 1, new BigDecimal("100.00"));
                    return true;
                } catch (InsufficientBalanceException e) {
                    return false;
                }
            });
        }

        long succeeded = race(buyers);

        assertThat(succeeded).isEqualTo(10);
        assertThat(cash()).isEqualByComparingTo("0");
        assertThat(count("SELECT COUNT(*) FROM transactions WHERE account_id = ?", accountId)).isEqualTo(10);
    }

    @Test
    void concurrentWithdrawalsNeverGoNegative() throws Exception {
        List<Callable<Boolean>> withdrawals = new ArrayList<>();
        for (int i = 0; i < 20; i++) {
            withdrawals.add(() -> accounts.adjustCash(accountId, new BigDecimal("-100.00")).isPresent());
        }

        long succeeded = race(withdrawals);

        assertThat(succeeded).isEqualTo(10);
        assertThat(cash()).isEqualByComparingTo("0");
    }

    private static long race(List<Callable<Boolean>> tasks) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(tasks.size());
        CountDownLatch start = new CountDownLatch(1);
        List<Future<Boolean>> futures = new ArrayList<>();
        for (Callable<Boolean> task : tasks) {
            futures.add(pool.submit(() -> { start.await(); return task.call(); }));
        }
        start.countDown();
        long succeeded = 0;
        for (Future<Boolean> f : futures) {
            if (f.get()) succeeded++;
        }
        pool.shutdown();
        return succeeded;
    }
}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && mvn -B -pl risk -am test-compile`
Expected: FAIL, compilation errors: `adjustCash` is not a member of `AccountRepository`, `executeBuy`/`executeSell` do not exist, `DatabaseConnection.use` does not exist.

- [ ] **Step 4: Write the Flyway migrations** (the schema ported from `db/migrations/V1..V5`; `NVARCHAR` becomes `VARCHAR`, `DATETIME2(3)` becomes `TIMESTAMP(3)` in UTC, identities become `GENERATED ALWAYS AS IDENTITY`)

`backend/risk/src/main/resources/db/migration/V1__schema.sql`:

```sql
-- FinRisk schema (PostgreSQL). All timestamps are UTC without time zone.

CREATE TABLE users (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name  VARCHAR(100) NOT NULL,
    email      VARCHAR(150) NOT NULL,
    created_at TIMESTAMP(3) NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE TABLE accounts (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users (id),
    account_name VARCHAR(100) NOT NULL,
    cash_balance NUMERIC(19,4) NOT NULL,
    created_at   TIMESTAMP(3) NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    CONSTRAINT ck_accounts_cash_nonnegative CHECK (cash_balance >= 0)
);

CREATE TABLE assets (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol        VARCHAR(20) NOT NULL,
    name          VARCHAR(150) NOT NULL,
    asset_type    VARCHAR(10) NOT NULL,
    current_price NUMERIC(19,4) NOT NULL,
    risk_level    VARCHAR(20) NOT NULL,
    created_at    TIMESTAMP(3) NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    CONSTRAINT ck_assets_type CHECK (asset_type IN ('STOCK', 'ETF', 'BOND', 'CRYPTO')),
    CONSTRAINT ck_assets_price_positive CHECK (current_price > 0),
    CONSTRAINT ck_assets_risk CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH')),
    CONSTRAINT uq_assets_symbol UNIQUE (symbol)
);

CREATE TABLE asset_details_stock (
    asset_id      BIGINT PRIMARY KEY REFERENCES assets (id) ON DELETE CASCADE,
    sector        VARCHAR(100) NOT NULL,
    exchange_name VARCHAR(100) NOT NULL
);

CREATE TABLE asset_details_etf (
    asset_id      BIGINT PRIMARY KEY REFERENCES assets (id) ON DELETE CASCADE,
    issuer        VARCHAR(150) NOT NULL,
    expense_ratio NUMERIC(19,6)
);

CREATE TABLE asset_details_bond (
    asset_id      BIGINT PRIMARY KEY REFERENCES assets (id) ON DELETE CASCADE,
    interest_rate NUMERIC(9,4) NOT NULL,
    maturity_date DATE NOT NULL,
    issuer        VARCHAR(150) NOT NULL
);

CREATE TABLE asset_details_crypto (
    asset_id   BIGINT PRIMARY KEY REFERENCES assets (id) ON DELETE CASCADE,
    blockchain VARCHAR(100) NOT NULL
);

CREATE TABLE transactions (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id       BIGINT NOT NULL REFERENCES accounts (id),
    asset_id         BIGINT NOT NULL REFERENCES assets (id),
    transaction_type VARCHAR(4) NOT NULL,
    quantity         INT NOT NULL,
    unit_price       NUMERIC(19,4) NOT NULL,
    transaction_date TIMESTAMP(3) NOT NULL,
    CONSTRAINT ck_transactions_type CHECK (transaction_type IN ('BUY', 'SELL')),
    CONSTRAINT ck_transactions_qty_positive CHECK (quantity > 0),
    CONSTRAINT ck_transactions_unit_price_positive CHECK (unit_price > 0)
);

CREATE TABLE asset_price_history (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id    BIGINT NOT NULL REFERENCES assets (id) ON DELETE CASCADE,
    price       NUMERIC(19,4) NOT NULL,
    recorded_at TIMESTAMP(3) NOT NULL,
    CONSTRAINT ck_price_history_price_positive CHECK (price > 0)
);

CREATE TABLE audit_logs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_name VARCHAR(100) NOT NULL,
    entity_id   BIGINT NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    created_at  TIMESTAMP(3) NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
```

`V2__indexes.sql` (the unique constraints on `users.email` and `assets.symbol` already create their indexes):

```sql
CREATE INDEX ix_accounts_user_id ON accounts (user_id);
CREATE INDEX ix_transactions_account_id ON transactions (account_id);
CREATE INDEX ix_transactions_asset_id ON transactions (asset_id);
CREATE INDEX ix_transactions_account_date ON transactions (account_id, transaction_date DESC);
CREATE INDEX ix_assets_asset_type ON assets (asset_type);
CREATE INDEX ix_price_history_asset_recorded ON asset_price_history (asset_id, recorded_at DESC);
CREATE INDEX ix_audit_logs_entity ON audit_logs (entity_name, entity_id);
```

`V3__views.sql`:

```sql
CREATE VIEW vw_portfolio_holdings AS
SELECT
    q.account_id,
    q.asset_id,
    a.symbol,
    a.name,
    a.asset_type,
    q.quantity,
    a.current_price,
    q.quantity::numeric(19,4) * a.current_price AS current_value
FROM (
    SELECT
        account_id,
        asset_id,
        SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE -quantity END) AS quantity
    FROM transactions
    GROUP BY account_id, asset_id
) AS q
INNER JOIN assets AS a ON a.id = q.asset_id
WHERE q.quantity > 0;

CREATE VIEW vw_portfolio_summary AS
SELECT
    ac.id AS account_id,
    ac.cash_balance,
    COALESCE(SUM(ph.current_value), 0::numeric(19,4)) AS total_holdings_value,
    ac.cash_balance + COALESCE(SUM(ph.current_value), 0::numeric(19,4)) AS total_account_value
FROM accounts AS ac
LEFT JOIN vw_portfolio_holdings AS ph ON ph.account_id = ac.id
GROUP BY ac.id, ac.cash_balance;

CREATE VIEW vw_portfolio_profit_loss AS
SELECT
    h.account_id,
    h.asset_id,
    ast.symbol,
    h.quantity,
    tt.buy_cost - tt.sell_proceeds AS net_invested,
    h.quantity::numeric(19,4) * ast.current_price AS current_value,
    (h.quantity::numeric(19,4) * ast.current_price) - (tt.buy_cost - tt.sell_proceeds) AS profit_loss,
    CASE
        WHEN (tt.buy_cost - tt.sell_proceeds) = 0 THEN NULL
        ELSE ((h.quantity::numeric(19,4) * ast.current_price) - (tt.buy_cost - tt.sell_proceeds))
             / NULLIF(tt.buy_cost - tt.sell_proceeds, 0) * 100.0
    END AS profit_loss_percent
FROM vw_portfolio_holdings AS h
INNER JOIN assets AS ast ON ast.id = h.asset_id
INNER JOIN (
    SELECT
        account_id,
        asset_id,
        SUM(CASE WHEN transaction_type = 'BUY' THEN quantity * unit_price ELSE 0 END) AS buy_cost,
        SUM(CASE WHEN transaction_type = 'SELL' THEN quantity * unit_price ELSE 0 END) AS sell_proceeds
    FROM transactions
    GROUP BY account_id, asset_id
) AS tt ON tt.account_id = h.account_id AND tt.asset_id = h.asset_id;
```

`V4__audit.sql` (one generic trigger function replaces the nine T-SQL triggers):

```sql
CREATE FUNCTION audit_row() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    rec    jsonb;
    entity BIGINT;
BEGIN
    rec := to_jsonb(CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END);
    entity := COALESCE((rec ->> 'id')::bigint, (rec ->> 'asset_id')::bigint);
    INSERT INTO audit_logs (entity_name, entity_id, action_type, description)
    VALUES (TG_TABLE_NAME, entity,
            CASE TG_OP WHEN 'INSERT' THEN 'CREATE' WHEN 'UPDATE' THEN 'UPDATE' ELSE 'DELETE' END,
            'CRUD operation captured by trigger');
    RETURN NULL;
END;
$$;

CREATE TRIGGER tr_audit_users AFTER INSERT OR UPDATE OR DELETE ON users FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER tr_audit_accounts AFTER INSERT OR UPDATE OR DELETE ON accounts FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER tr_audit_assets AFTER INSERT OR UPDATE OR DELETE ON assets FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER tr_audit_asset_details_stock AFTER INSERT OR UPDATE OR DELETE ON asset_details_stock FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER tr_audit_asset_details_etf AFTER INSERT OR UPDATE OR DELETE ON asset_details_etf FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER tr_audit_asset_details_bond AFTER INSERT OR UPDATE OR DELETE ON asset_details_bond FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER tr_audit_asset_details_crypto AFTER INSERT OR UPDATE OR DELETE ON asset_details_crypto FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER tr_audit_transactions AFTER INSERT OR UPDATE OR DELETE ON transactions FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER tr_audit_asset_price_history AFTER INSERT OR UPDATE OR DELETE ON asset_price_history FOR EACH ROW EXECUTE FUNCTION audit_row();
```

`backend/risk/src/main/resources/db/dev/V100__dev_seed.sql` (loaded only when the `dev` profile adds `classpath:db/dev` to the Flyway locations; see Task 10):

```sql
INSERT INTO users (full_name, email)
SELECT 'User ' || n, 'user' || n || '@example.com' FROM generate_series(1, 10) AS n;

INSERT INTO accounts (user_id, account_name, cash_balance)
SELECT id, 'Main account', 10000.0000 FROM users;

INSERT INTO assets (symbol, name, asset_type, current_price, risk_level) VALUES
    ('AAPL',    'Apple Inc.',         'STOCK',  200.0000, 'MEDIUM'),
    ('MSFT',    'Microsoft Corp.',    'STOCK',  420.0000, 'MEDIUM'),
    ('JPM',     'JPMorgan Chase',     'STOCK',  200.0000, 'MEDIUM'),
    ('SPY',     'SPDR S&P 500 ETF',   'ETF',    540.0000, 'LOW'),
    ('QQQ',     'Invesco QQQ Trust',  'ETF',    480.0000, 'MEDIUM'),
    ('BTC-USD', 'Bitcoin',            'CRYPTO', 60000.0000, 'VERY_HIGH');

INSERT INTO asset_details_stock (asset_id, sector, exchange_name)
SELECT id, CASE symbol WHEN 'JPM' THEN 'Financial Services' ELSE 'Technology' END,
       CASE symbol WHEN 'JPM' THEN 'NYSE' ELSE 'NASDAQ' END
FROM assets WHERE symbol IN ('AAPL', 'MSFT', 'JPM');

INSERT INTO asset_details_etf (asset_id, issuer, expense_ratio)
SELECT id, CASE symbol WHEN 'SPY' THEN 'State Street' ELSE 'Invesco' END, 0.000900 FROM assets WHERE asset_type = 'ETF';

INSERT INTO asset_details_crypto (asset_id, blockchain) SELECT id, 'Bitcoin' FROM assets WHERE symbol = 'BTC-USD';

-- 60 days of deterministic price history (a gentle wave around the current price)
INSERT INTO asset_price_history (asset_id, price, recorded_at)
SELECT a.id,
       round((a.current_price * (1 + 0.02 * sin(d / 3.0 + a.id)))::numeric, 4),
       (now() AT TIME ZONE 'utc')::date - d
FROM assets a CROSS JOIN generate_series(1, 60) AS d;

-- account 1 holds 10 AAPL and 10 SPY
INSERT INTO transactions (account_id, asset_id, transaction_type, quantity, unit_price, transaction_date)
SELECT 1, id, 'BUY', 10, current_price, (now() AT TIME ZONE 'utc') FROM assets WHERE symbol IN ('AAPL', 'SPY');

UPDATE accounts
SET cash_balance = cash_balance - (SELECT COALESCE(SUM(quantity * unit_price), 0) FROM transactions WHERE account_id = 1)
WHERE id = 1;
```

- [ ] **Step 5: Replace `DatabaseConnection`; remove the stored-procedure plumbing**

Replace `backend/risk/src/main/java/com/finrisk/shared/DatabaseConnection.java`:

```java
package com.finrisk.shared;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Static handle on the application's DataSource for the JDBC helpers in {@link Db}.
 * Spring creates and owns the pool; {@link DataSourceBridge} hands it over at startup.
 */
public final class DatabaseConnection {

    private static final AtomicReference<DataSource> INSTANCE = new AtomicReference<>();

    private DatabaseConnection() {}

    public static void use(DataSource dataSource) {
        INSTANCE.set(dataSource);
    }

    public static Connection getConnection() throws SQLException {
        DataSource dataSource = INSTANCE.get();
        if (dataSource == null) {
            throw new IllegalStateException("DataSource is not configured");
        }
        return dataSource.getConnection();
    }
}
```

Create `backend/risk/src/main/java/com/finrisk/shared/DataSourceBridge.java`:

```java
package com.finrisk.shared;

import org.springframework.stereotype.Component;

import javax.sql.DataSource;

/** Gives Spring's DataSource to the static JDBC helpers as soon as it exists. */
@Component
class DataSourceBridge {

    DataSourceBridge(DataSource dataSource) {
        DatabaseConnection.use(dataSource);
    }
}
```

Delete `backend/risk/src/main/java/com/finrisk/shared/JdbcSqlExceptionMapper.java`. In `shared/Db.java` delete the `call(String sql, Object... params)` method, the private `bindCall(...)` method, the `CALL_FAILED_PREFIX` constant and the `import java.sql.CallableStatement;` line.

- [ ] **Step 6: Port the SQL dialect in the seven repositories**

Run the mechanical part from the repo root:

```bash
cd backend/risk/src/main/java/com/finrisk/portfolio/infrastructure
perl -pi -e 's/\bdbo\.//g; s/\bN\x27/\x27/g; s/SYSUTCDATETIME\(\)/(now() AT TIME ZONE \x27utc\x27)/g; s/"23000"\.equals\(e\.getSQLState\(\)\) \|\| e\.getErrorCode\(\) == 2627 \|\| e\.getErrorCode\(\) == 2601/"23505".equals(e.getSQLState())/' Postgres*.java
cd -
```

Then make these hand edits (the repository classes keep their SQL in text blocks):

1. **`PostgresUserRepository`, `PostgresAccountRepository`, `PostgresAssetRepository`**: the three `INSERT` statements end with a second statement. Replace each `…;\n SELECT CAST(SCOPE_IDENTITY() AS BIGINT);` with `RETURNING id`. For example `INSERT_ASSET` becomes:

   ```java
   private static final String INSERT_ASSET =
           """
           INSERT INTO assets (symbol, name, asset_type, current_price, risk_level, created_at)
           VALUES (?, ?, ?, ?, ?, (now() AT TIME ZONE 'utc'))
           RETURNING id
           """;
   ```
   and the user and account inserts end `... VALUES (?, ?, (now() AT TIME ZONE 'utc')) RETURNING id` and `... VALUES (?, ?, ?, (now() AT TIME ZONE 'utc')) RETURNING id` (drop the trailing `;` and the `SELECT`).
2. **`PostgresUserRepository.pageUsers`**: the prefix filter becomes
   `" WHERE LOWER(email) LIKE LOWER(?) || '%' ESCAPE '\\'"`.
3. **`PostgresAssetPriceHistoryRepository`**:
   - `latestPrices`: `SELECT price FROM asset_price_history WHERE asset_id = ? ORDER BY recorded_at DESC LIMIT ?`, and swap the arguments to `assetId, Math.max(limit, 1)`.
   - `upsertForDate`: replace the `MERGE` with an update-then-insert in one transaction:

   ```java
   @Override
   public void upsertForDate(long assetId, LocalDate date, BigDecimal price) {
       Db.inTx(c -> {
           int updated = Db.update(c,
                   "UPDATE asset_price_history SET price = ? WHERE asset_id = ? AND CAST(recorded_at AS DATE) = ?",
                   price, assetId, Date.valueOf(date));
           if (updated == 0) {
               Db.update(c,
                       "INSERT INTO asset_price_history (asset_id, price, recorded_at) VALUES (?, ?, CAST(? AS TIMESTAMP))",
                       assetId, price, Date.valueOf(date));
           }
           return null;
       });
   }
   ```
4. **`PostgresTransactionRepository.findLatest`**: `SELECT id, ... FROM transactions WHERE ... ORDER BY id DESC LIMIT 1` (remove `TOP 1`).

`OFFSET ? ROWS FETCH NEXT ? ROWS ONLY` is standard SQL that PostgreSQL accepts, so every paged query stays as it is.

- [ ] **Step 7: Replace the stored procedures and the read-modify-write cash update with atomic Java**

In `portfolio/domain/repository/AccountRepository.java` replace `void updateCashBalance(Long id, BigDecimal newBalance);` with:

```java
    /**
     * Atomically adds {@code delta} (negative to withdraw) and returns the new balance.
     * Empty when the account does not exist or the balance would go below zero.
     */
    Optional<BigDecimal> adjustCash(long accountId, BigDecimal delta);
```
(add `import java.util.Optional;`).

In `portfolio/infrastructure/PostgresAccountRepository.java` replace the `updateCashBalance` method with:

```java
    @Override
    public Optional<BigDecimal> adjustCash(long accountId, BigDecimal delta) {
        return Db.findOne(
                """
                UPDATE accounts SET cash_balance = cash_balance + ?
                WHERE id = ? AND cash_balance + ? >= 0
                RETURNING cash_balance
                """,
                rs -> rs.getBigDecimal(1),
                delta,
                accountId,
                delta);
    }
```
(add `import java.util.Optional;` if missing).

In `portfolio/application/AccountService.java` replace the bodies of `deposit` and `withdraw`:

```java
    public AccountResponse deposit(long accountId, CashMovementRequest req) {
        Account a = requireAccount(accountId);
        BigDecimal next = accountRepository.adjustCash(accountId, req.amount())
                .orElseThrow(() -> new AccountNotFoundException("Account not found"));
        return AccountMapper.toResponse(a.withCashBalance(next));
    }

    public AccountResponse withdraw(long accountId, CashMovementRequest req) {
        Account a = requireAccount(accountId);
        BigDecimal next = accountRepository.adjustCash(accountId, req.amount().negate())
                .orElseThrow(() -> new InsufficientBalanceException("Insufficient cash balance"));
        return AccountMapper.toResponse(a.withCashBalance(next));
    }
```

In `portfolio/domain/repository/TransactionRepository.java` rename `executeBuyProcedure` to `executeBuy` and `executeSellProcedure` to `executeSell` (same parameters). In `portfolio/application/TransactionService.java` update the two calls (`transactionRepository.executeBuy(...)`, `.executeSell(...)`).

In `portfolio/infrastructure/PostgresTransactionRepository.java` replace the two procedure methods with:

```java
    @Override
    public void executeBuy(long accountId, long assetId, int quantity, BigDecimal unitPrice) {
        BigDecimal total = unitPrice.multiply(BigDecimal.valueOf(quantity)).setScale(4, RoundingMode.HALF_UP);
        Db.inTx(c -> {
            // Row lock on the account serialises every trade and cash movement for it.
            BigDecimal cash = Db.findOne(c, "SELECT cash_balance FROM accounts WHERE id = ? FOR UPDATE",
                            rs -> rs.getBigDecimal(1), accountId)
                    .orElseThrow(() -> new AccountNotFoundException("Account not found"));
            requireAsset(c, assetId);
            if (cash.compareTo(total) < 0) {
                throw new InsufficientBalanceException("Insufficient cash balance");
            }
            Db.update(c, "UPDATE accounts SET cash_balance = cash_balance - ? WHERE id = ?", total, accountId);
            recordTrade(c, accountId, assetId, "BUY", quantity, unitPrice);
            return null;
        });
    }

    @Override
    public void executeSell(long accountId, long assetId, int quantity, BigDecimal unitPrice) {
        BigDecimal total = unitPrice.multiply(BigDecimal.valueOf(quantity)).setScale(4, RoundingMode.HALF_UP);
        Db.inTx(c -> {
            Db.findOne(c, "SELECT id FROM accounts WHERE id = ? FOR UPDATE", rs -> rs.getLong(1), accountId)
                    .orElseThrow(() -> new AccountNotFoundException("Account not found"));
            requireAsset(c, assetId);
            long owned = Db.queryLong(c,
                    """
                    SELECT COALESCE(SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE -quantity END), 0)
                    FROM transactions WHERE account_id = ? AND asset_id = ?
                    """,
                    accountId, assetId);
            if (owned < quantity) {
                throw new InsufficientQuantityException("Insufficient asset quantity");
            }
            Db.update(c, "UPDATE accounts SET cash_balance = cash_balance + ? WHERE id = ?", total, accountId);
            recordTrade(c, accountId, assetId, "SELL", quantity, unitPrice);
            return null;
        });
    }

    private static void requireAsset(Connection c, long assetId) {
        Db.findOne(c, "SELECT id FROM assets WHERE id = ?", rs -> rs.getLong(1), assetId)
                .orElseThrow(() -> new AssetNotFoundException("Asset not found"));
    }

    private static void recordTrade(Connection c, long accountId, long assetId, String type, int quantity, BigDecimal unitPrice) {
        long transactionId = Db.insertReturning(c,
                """
                INSERT INTO transactions (account_id, asset_id, transaction_type, quantity, unit_price, transaction_date)
                VALUES (?, ?, ?, ?, ?, (now() AT TIME ZONE 'utc'))
                RETURNING id
                """,
                rs -> rs.getLong(1), accountId, assetId, type, quantity, unitPrice);
        Db.exec(c,
                "INSERT INTO audit_logs (entity_name, entity_id, action_type, description) VALUES ('TRANSACTION', ?, ?, ?)",
                transactionId, type + "_TRANSACTION_CREATED", ("BUY".equals(type) ? "Buy" : "Sell") + " trade persisted");
    }
```

Add the imports this needs: `java.math.RoundingMode`, `java.sql.Connection`, `com.finrisk.portfolio.domain.exception.{AccountNotFoundException,AssetNotFoundException,InsufficientBalanceException,InsufficientQuantityException}`.

- [ ] **Step 8: Confirm no SQL Server syntax is left**

Run:

```bash
grep -rnE "dbo\.|N'|TOP \(|TOP [0-9]|SCOPE_IDENTITY|SYSUTCDATETIME|WITH \(|ISNULL\(|GETDATE|MERGE|EXEC |\{call|CallableStatement|updateCashBalance|executeBuyProcedure|executeSellProcedure" backend/risk/src || echo "clean"
```

Expected: `clean`.

- [ ] **Step 9: Run the unit tests, then the integration tests**

Run: `cd backend && mvn -B -pl risk -am test`
Expected: `AccountServiceTest` `Tests run: 4`; the module total is `100` (96 + 4); `BUILD SUCCESS`.

Run (needs Docker running): `cd backend && mvn -B -pl risk -am verify`
Expected: failsafe runs `TradeExecutionIT` with `Tests run: 6, Failures: 0, Errors: 0`, including the two concurrency tests that must show exactly 10 successes, and `BUILD SUCCESS`.

- [ ] **Step 10: Commit**

```bash
git add backend/risk
git commit -m "feat(risk): PostgreSQL with Flyway, atomic cash and trades replace stored procedures"
```

---

## Phase D: The runnable app and its guard rails

### Task 10: `app` module: Spring Boot entry point, configuration, full-stack test

**Files:**
- Modify: `backend/pom.xml` (add `<module>app</module>`)
- Create: `backend/app/pom.xml`
- Create: `backend/app/src/main/java/com/finrisk/app/FinRiskApplication.java`
- Create: `backend/app/src/main/resources/{application.yml,application-dev.yml}`
- Test: `backend/app/src/test/java/com/finrisk/app/{StubMarketData,FullStackIT}.java`

**Interfaces:**
- Consumes: the `valuation`, `risk` and `marketdata` modules; the `MarketData` bean from `MarketDataConfiguration` (Task 4); Flyway files and the dev seed (Task 9).
- Produces: the runnable jar `backend/app/target/finrisk.jar`; environment variables `PORT`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_POOL_SIZE`, `FMP_API_KEY`, `FMP_BASE_URL`, `MARKETDATA_SOURCES`, `YAHOO_ENABLED`, `SPRING_PROFILES_ACTIVE` (`dev` adds the seed data); health endpoint `GET /actuator/health`.

- [ ] **Step 1: Register the module and create its POM**

In `backend/pom.xml` set:

```xml
  <modules>
    <module>marketdata-api</module>
    <module>marketdata</module>
    <module>valuation</module>
    <module>risk</module>
    <module>app</module>
  </modules>
```

`backend/app/pom.xml`:

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
  <artifactId>app</artifactId>
  <description>The deployable FinRisk backend: wires Data, Valuation, Portfolio and Risk together.</description>

  <dependencies>
    <dependency>
      <groupId>com.finrisk</groupId>
      <artifactId>valuation</artifactId>
    </dependency>
    <dependency>
      <groupId>com.finrisk</groupId>
      <artifactId>risk</artifactId>
    </dependency>
    <dependency>
      <groupId>com.finrisk</groupId>
      <artifactId>marketdata</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-actuator</artifactId>
    </dependency>

    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>io.rest-assured</groupId>
      <artifactId>rest-assured</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.testcontainers</groupId>
      <artifactId>postgresql</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.testcontainers</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>com.tngtech.archunit</groupId>
      <artifactId>archunit-junit5</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>

  <build>
    <finalName>finrisk</finalName>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-failsafe-plugin</artifactId>
        <configuration>
          <includes>
            <include>**/*IT.java</include>
          </includes>
        </configuration>
        <executions>
          <execution>
            <goals>
              <goal>integration-test</goal>
              <goal>verify</goal>
            </goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 2: Write the failing full-stack test** (the whole app against a real Postgres, with market data stubbed so nothing touches the network)

`backend/app/src/test/java/com/finrisk/app/StubMarketData.java`:

```java
package com.finrisk.app;

import com.finrisk.marketdata.CompanyProfile;
import com.finrisk.marketdata.EtfHolding;
import com.finrisk.marketdata.Fundamentals;
import com.finrisk.marketdata.MarketData;
import com.finrisk.marketdata.Peer;
import com.finrisk.marketdata.PricePoint;
import com.finrisk.marketdata.Quote;
import com.finrisk.marketdata.ValuationMetric;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/** Canned market data so the full-stack test never touches the network. */
final class StubMarketData implements MarketData {

    @Override
    public List<PricePoint> fetchDailyPrices(String symbol, int days) {
        List<PricePoint> prices = new ArrayList<>();
        LocalDate today = LocalDate.now();
        for (int i = 0; i < Math.min(days, 90); i++) {
            prices.add(new PricePoint(today.minusDays(i), BigDecimal.valueOf(100 + 2 * Math.sin(i / 3.0))));
        }
        return prices;
    }

    @Override
    public CompanyProfile fetchProfile(String symbol) {
        return switch (symbol) {
            case "AAPL", "MSFT" -> new CompanyProfile(symbol, "Technology", "Software", symbol);
            case "JPM" -> new CompanyProfile(symbol, "Financial Services", "Banks", symbol);
            default -> CompanyProfile.unknown(symbol);
        };
    }

    @Override
    public List<EtfHolding> fetchEtfHoldings(String etfSymbol) {
        return switch (etfSymbol) {
            case "SPY" -> List.of(
                    new EtfHolding("AAPL", "Apple", new BigDecimal("0.070")),
                    new EtfHolding("MSFT", "Microsoft", new BigDecimal("0.065")));
            case "QQQ" -> List.of(
                    new EtfHolding("AAPL", "Apple", new BigDecimal("0.090")),
                    new EtfHolding("MSFT", "Microsoft", new BigDecimal("0.080")));
            default -> List.of();
        };
    }

    @Override
    public Optional<Quote> fetchQuote(String symbol) {
        return "AAPL".equals(symbol)
                ? Optional.of(new Quote("AAPL", new BigDecimal("200"), new BigDecimal("15000000000"), new BigDecimal("0.96")))
                : Optional.empty();
    }

    @Override
    public Optional<Fundamentals> fetchFundamentals(String symbol) { return Optional.empty(); }

    @Override
    public Optional<BigDecimal> fetchMetric(String symbol, ValuationMetric metric) { return Optional.empty(); }

    @Override
    public List<Peer> fetchPeers(String sector, int limit) { return List.of(); }
}
```

`backend/app/src/test/java/com/finrisk/app/FullStackIT.java`:

```java
package com.finrisk.app;

import com.finrisk.marketdata.MarketData;
import io.restassured.RestAssured;
import io.restassured.http.ContentType;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.TimeZone;

import static io.restassured.RestAssured.given;
import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.allOf;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;
import static org.hamcrest.Matchers.lessThan;

/** Needs Docker. Boots the real application on a real Postgres with the dev seed data. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("dev")
@Testcontainers
class FullStackIT {

    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine");

    @DynamicPropertySource
    static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
    }

    @TestConfiguration
    static class OfflineMarketData {
        @Bean
        @Primary
        MarketData offlineMarketData() {
            return new StubMarketData();
        }
    }

    @LocalServerPort int port;

    @BeforeAll
    static void utc() {
        TimeZone.setDefault(TimeZone.getTimeZone("UTC"));
    }

    @BeforeEach
    void rest() {
        RestAssured.baseURI = "http://localhost";
        RestAssured.port = port;
    }

    @Test
    void healthIsUp() {
        given().get("/actuator/health").then().statusCode(200).body("status", equalTo("UP"));
    }

    @Test
    void theSeededPortfolioIsServed() {
        given().get("/api/v1/accounts/1/portfolio")
                .then().statusCode(200)
                .body(containsString("AAPL"))
                .body(containsString("SPY"));
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "portfolio", "profit-loss", "risk", "beta", "sector-exposure", "diversification",
            "correlation", "drawdown", "alpha", "downside", "etf-look-through", "etf-overlap"})
    void everyAccountEndpointAnswersForTheSeededAccount(String path) {
        given().get("/api/v1/accounts/1/" + path).then().statusCode(200);
    }

    @Test
    void aDepositChangesTheBalanceAtomically() {
        double balance = given().contentType(ContentType.JSON).body("{\"amount\": 50.00}")
                .post("/api/v1/accounts/3/deposit")
                .then().statusCode(200)
                .extract().jsonPath().getDouble("cashBalance");

        assertThat(balance).isEqualTo(10050.0);
    }

    @Test
    void buyingThroughHttpCreatesAPosition() {
        given().contentType(ContentType.JSON)
                .body("{\"accountId\":2,\"assetId\":1,\"quantity\":1,\"unitPrice\":10.00}")
                .post("/api/v1/transactions/buy")
                .then().statusCode(allOf(greaterThanOrEqualTo(200), lessThan(300)));

        given().get("/api/v1/accounts/2/portfolio").then().statusCode(200).body(containsString("AAPL"));
    }

    @Test
    void valuationIsServedAndUnknownTickersAre404() {
        given().contentType(ContentType.JSON)
                .body("""
                        {"ticker":"AAPL","fcf":100,"sharesOutstanding":10,"projectionYears":2,"growthRate":0,
                         "discountRate":0.10,"terminalGrowthRate":0}""")
                .post("/api/v1/valuation/dcf")
                .then().statusCode(200).body("ticker", equalTo("AAPL"));

        given().contentType(ContentType.JSON)
                .body("""
                        {"ticker":"ZZZ","fcf":100,"sharesOutstanding":10,"discountRate":0.10,"terminalGrowthRate":0}""")
                .post("/api/v1/valuation/dcf")
                .then().statusCode(404).body("code", equalTo("TICKER_NOT_FOUND"));
    }
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd backend && mvn -B -pl app -am verify`
Expected: FAIL, `FullStackIT` cannot start: "Unable to find a @SpringBootConfiguration" (there is no application class yet).

- [ ] **Step 4: Write the application class and configuration**

`backend/app/src/main/java/com/finrisk/app/FinRiskApplication.java`:

```java
package com.finrisk.app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication(scanBasePackages = "com.finrisk")
public class FinRiskApplication {

    public static void main(String[] args) {
        SpringApplication.run(FinRiskApplication.class, args);
    }
}
```

`backend/app/src/main/resources/application.yml`:

```yaml
spring:
  application:
    name: finrisk-backend
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:finrisk}
    username: ${DB_USER:finrisk}
    password: ${DB_PASSWORD:finrisk}
    hikari:
      maximum-pool-size: ${DB_POOL_SIZE:10}
  flyway:
    locations: classpath:db/migration
  jackson:
    serialization:
      write-dates-as-timestamps: false

server:
  port: ${PORT:8080}
  shutdown: graceful

management:
  endpoints:
    web:
      exposure:
        include: health
  endpoint:
    health:
      probes:
        enabled: true

logging:
  level:
    com.finrisk: INFO

marketdata:
  sources: ${MARKETDATA_SOURCES:fmp,yahoo}
  fmp:
    api-key: ${FMP_API_KEY:}
    base-url: ${FMP_BASE_URL:https://financialmodelingprep.com/api/v3}
  yahoo:
    enabled: ${YAHOO_ENABLED:true}
```

`backend/app/src/main/resources/application-dev.yml` (adds the seed migration; never used on Render):

```yaml
spring:
  flyway:
    locations: classpath:db/migration,classpath:db/dev
```

- [ ] **Step 5: Run the test to verify it passes**

Run (needs Docker): `cd backend && mvn -B verify`
Expected: all modules green; `FullStackIT` `Tests run: 17` (1 + 1 + 12 parameterised + 1 + 1 + 1), `TradeExecutionIT` 6, `BUILD SUCCESS`. The jar exists: `ls backend/app/target/finrisk.jar`.

If an account endpoint answers 4xx or 5xx, read its response body: the seed gives account 1 two holdings (AAPL, SPY) and 60 days of history, so every analytics endpoint has data. Fix the cause; do not loosen the assertion.

- [ ] **Step 6: Commit**

```bash
git add backend/pom.xml backend/app
git commit -m "feat(app): Spring Boot entry point, configuration and full-stack test"
```

---

### Task 11: Architecture rules (ArchUnit)

**Files:**
- Test: `backend/app/src/test/java/com/finrisk/app/ArchitectureTest.java`

**Interfaces:**
- Consumes: the package layout from Tasks 5-9.
- Produces: build-breaking rules for the boundaries this refactor creates.

- [ ] **Step 1: Write the rules**

`backend/app/src/test/java/com/finrisk/app/ArchitectureTest.java`:

```java
package com.finrisk.app;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

/**
 * The boundaries of the monolith. Maven already stops risk and valuation from importing the market data adapters
 * (they do not depend on that module). These rules guard the boundaries Maven cannot see: packages inside one module.
 */
@AnalyzeClasses(packages = "com.finrisk", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

    @ArchTest
    static final ArchRule valuationKnowsNothingOfPortfolioRiskOrPersistence =
            noClasses().that().resideInAPackage("com.finrisk.valuation..")
                    .should().dependOnClassesThat()
                    .resideInAnyPackage("com.finrisk.portfolio..", "com.finrisk.risk..", "com.finrisk.shared..");

    @ArchTest
    static final ArchRule portfolioRiskAndSharedKnowNothingOfValuation =
            noClasses().that().resideInAnyPackage("com.finrisk.portfolio..", "com.finrisk.risk..", "com.finrisk.shared..")
                    .should().dependOnClassesThat().resideInAPackage("com.finrisk.valuation..");

    @ArchTest
    static final ArchRule portfolioDoesNotDependOnRisk =
            noClasses().that().resideInAPackage("com.finrisk.portfolio..")
                    .should().dependOnClassesThat().resideInAPackage("com.finrisk.risk..");

    @ArchTest
    static final ArchRule riskUsesPortfolioOnlyThroughItsDomain =
            noClasses().that().resideInAPackage("com.finrisk.risk..")
                    .should().dependOnClassesThat().resideInAnyPackage(
                            "com.finrisk.portfolio.application..",
                            "com.finrisk.portfolio.infrastructure..",
                            "com.finrisk.portfolio.web..");

    @ArchTest
    static final ArchRule sharedKernelDependsOnNoContext =
            noClasses().that().resideInAPackage("com.finrisk.shared..")
                    .should().dependOnClassesThat()
                    .resideInAnyPackage("com.finrisk.portfolio..", "com.finrisk.risk..", "com.finrisk.valuation..");

    @ArchTest
    static final ArchRule domainLayersAreFreeOfFrameworksAndOuterLayers =
            noClasses().that().resideInAnyPackage(
                            "com.finrisk.valuation.domain..", "com.finrisk.portfolio.domain..", "com.finrisk.risk.domain..")
                    .should().dependOnClassesThat().resideInAnyPackage(
                            "org.springframework..", "jakarta..", "java.sql..", "javax.sql..",
                            "com.finrisk..application..", "com.finrisk..web..", "com.finrisk..infrastructure..");
}
```

- [ ] **Step 2: Run it**

Run: `cd backend && mvn -B -pl app -am test -Dtest=ArchitectureTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: `Tests run: 6, Failures: 0`. These rules hold on the code as moved in Task 8 because the factories went to `portfolio.application` and the read models (`Holding`, `AssetPricePoint`, `HoldingProfitLoss`) went to `portfolio.domain`.

If a rule fails, ArchUnit prints the offending class and the line that violates it. Fix the code by moving the dependency or the class to the right layer. Never weaken a rule to make it pass.

- [ ] **Step 3: Prove a rule can fail** (a rule that cannot fail is worth nothing)

Temporarily add `import org.springframework.stereotype.Service;` and an `@Service` annotation on the class in `backend/valuation/src/main/java/com/finrisk/valuation/domain/Rates.java`; run the same command; expect `domainLayersAreFreeOfFrameworksAndOuterLayers` to FAIL and name `Rates`. Then revert with `git checkout -- backend/valuation` and re-run to see it pass again.

- [ ] **Step 4: Commit**

```bash
git add backend/app/src/test/java/com/finrisk/app/ArchitectureTest.java
git commit -m "test(app): ArchUnit rules for context and layer boundaries"
```

---

## Phase E: Delivery

### Task 12: Dockerfile, local docker-compose, environment template

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`
- Create: `docker-compose.yml`, `.env.example` (repo root)

**Interfaces:**
- Consumes: `backend/app/target/finrisk.jar` produced by the build inside the Dockerfile; the environment variables from Task 10; `hybrid-rag/Dockerfile` (existing: Python 3.11, uvicorn on 8000) and its environment variables from its README (`LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `RAG_MODE`, `CACHE_DIR`).
- Produces: image `backend` (port 8080), a compose stack of `postgres` + `backend` + `rag`.

- [ ] **Step 1: Write the Docker files**

`backend/Dockerfile`:

```dockerfile
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY . .
RUN mvn -B -q -DskipTests package

FROM eclipse-temurin:21-jre
RUN useradd --system --uid 10001 finrisk
WORKDIR /app
COPY --from=build /build/app/target/finrisk.jar /app/finrisk.jar
# UTC everywhere: timestamps are stored as UTC without a zone.
ENV TZ=UTC \
    JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75 -Duser.timezone=UTC"
USER finrisk
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/finrisk.jar"]
```

`backend/.dockerignore`:

```
**/target
.git
.idea
*.iml
```

`.env.example` (repo root; copy to `.env`, which stays untracked):

```bash
# --- Database (the compose postgres uses these; on Render they come from the managed database) ---
DB_NAME=finrisk
DB_USER=finrisk
DB_PASSWORD=change-me

# --- Backend ---
# "dev" loads seed data (10 users, 6 assets, price history). Use "prod" for an empty database.
BACKEND_PROFILE=dev
# Market data sources are tried in this order. FMP is skipped when FMP_API_KEY is empty.
MARKETDATA_SOURCES=fmp,yahoo
FMP_API_KEY=
# Yahoo is an unofficial fallback (not cleared for redistribution). Set false to turn it off.
YAHOO_ENABLED=true

# --- RAG service ---
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:3b
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash
RAG_MODE=hybrid
```

`docker-compose.yml`:

```yaml
# Local run: docker compose up --build
# Render does not run compose files; see render.yaml for the deployed equivalent.
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME:-finrisk}
      POSTGRES_USER: ${DB_USER:-finrisk}
      POSTGRES_PASSWORD: ${DB_PASSWORD:?set DB_PASSWORD in .env}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      SPRING_PROFILES_ACTIVE: ${BACKEND_PROFILE:-dev}
      DB_HOST: postgres
      DB_PORT: "5432"
      DB_NAME: ${DB_NAME:-finrisk}
      DB_USER: ${DB_USER:-finrisk}
      DB_PASSWORD: ${DB_PASSWORD:?set DB_PASSWORD in .env}
      MARKETDATA_SOURCES: ${MARKETDATA_SOURCES:-fmp,yahoo}
      FMP_API_KEY: ${FMP_API_KEY:-}
      YAHOO_ENABLED: ${YAHOO_ENABLED:-true}
    ports:
      - "8080:8080"

  rag:
    build: ./hybrid-rag
    environment:
      LLM_PROVIDER: ${LLM_PROVIDER:-ollama}
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
      OLLAMA_MODEL: ${OLLAMA_MODEL:-qwen2.5:3b}
      GEMINI_API_KEY: ${GEMINI_API_KEY:-}
      GEMINI_MODEL: ${GEMINI_MODEL:-gemini-1.5-flash}
      RAG_MODE: ${RAG_MODE:-hybrid}
      CACHE_DIR: /app/cache
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ragcache:/app/cache
    ports:
      - "8000:8000"

volumes:
  pgdata:
  ragcache:
```

- [ ] **Step 2: Validate the compose file**

Run: `cp .env.example .env && docker compose config --quiet && echo compose-ok`
Expected: `compose-ok` (a missing `DB_PASSWORD` would fail here with "set DB_PASSWORD in .env").

- [ ] **Step 3: Build and run the stack**

Run: `docker compose up --build -d` (first build takes several minutes: Maven, and the RAG image downloads Python packages)

Run: `docker compose ps`
Expected: `postgres` is `healthy`; `backend` and `rag` are `running`.

- [ ] **Step 4: Smoke-test it**

```bash
curl -sf localhost:8080/actuator/health
curl -sf localhost:8080/api/v1/accounts/1/portfolio | head -c 300; echo
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8080/api/v1/valuation/dcf \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"AAPL","fcf":100,"sharesOutstanding":10,"discountRate":0.10,"terminalGrowthRate":0.02}'
curl -sf localhost:8000/health
```

Expected: the first prints `{"status":"UP"...}`; the second prints JSON containing `AAPL`; the third prints `200` when FMP or Yahoo is reachable and `404` when neither is (that is a correct answer, "no market data"; a `500` is a bug); the fourth prints the RAG health JSON.

- [ ] **Step 5: Tear down and commit**

```bash
docker compose down -v
git add backend/Dockerfile backend/.dockerignore docker-compose.yml .env.example
git commit -m "build: backend Dockerfile, local compose stack, env template"
```

(`.env` is not added; it is created from the template and must stay untracked.)

---

### Task 13: Render Blueprint

**Files:**
- Create: `render.yaml` (repo root)

**Interfaces:**
- Consumes: `backend/Dockerfile` (Task 12), `hybrid-rag/Dockerfile`, `landing/` (Vite app: `npm ci && npm run build` writes `landing/dist`), the environment variables from Tasks 10 and 12.
- Produces: one Render Blueprint creating a Postgres database, the backend web service, the RAG private service and the landing static site.

- [ ] **Step 1: Write the Blueprint**

`render.yaml`:

```yaml
# Render does not run docker-compose. This Blueprint is the deployed equivalent of docker-compose.yml:
# one Docker image per service, built from the same Dockerfiles, wired over Render's private network.
databases:
  - name: finrisk-db
    databaseName: finrisk
    user: finrisk
    region: oregon
    plan: basic-256mb
    ipAllowList: []            # internal connections only; nothing public

services:
  # --- Java monolith: Data, Valuation, Portfolio, Risk ---
  - type: web
    name: finrisk-backend
    runtime: docker
    region: oregon
    plan: starter              # 512 MB: the JVM is capped at 75% of container memory by the image
    dockerfilePath: ./backend/Dockerfile
    dockerContext: ./backend
    healthCheckPath: /actuator/health
    envVars:
      - key: PORT
        value: "8080"
      - key: DB_HOST
        fromDatabase: { name: finrisk-db, property: host }
      - key: DB_PORT
        fromDatabase: { name: finrisk-db, property: port }
      - key: DB_NAME
        fromDatabase: { name: finrisk-db, property: database }
      - key: DB_USER
        fromDatabase: { name: finrisk-db, property: user }
      - key: DB_PASSWORD
        fromDatabase: { name: finrisk-db, property: password }
      - key: MARKETDATA_SOURCES
        value: fmp,yahoo
      - key: YAHOO_ENABLED
        value: "true"
      - key: FMP_API_KEY
        sync: false            # set in the dashboard; never committed

  # --- Python RAG service (private: reachable only from other services on the private network) ---
  - type: pserv
    name: finrisk-rag
    runtime: docker
    region: oregon
    plan: standard             # 2 GB: the embedding and reranker models do not fit in 512 MB
    dockerfilePath: ./hybrid-rag/Dockerfile
    dockerContext: ./hybrid-rag
    disk:
      name: rag-cache
      mountPath: /app/cache
      sizeGB: 1
    envVars:
      - key: PORT
        value: "8000"
      - key: LLM_PROVIDER
        value: gemini          # Ollama is not available on Render
      - key: GEMINI_MODEL
        value: gemini-1.5-flash
      - key: GEMINI_API_KEY
        sync: false
      - key: RAG_MODE
        value: hybrid
      - key: CACHE_DIR
        value: /app/cache

  # --- Marketing site ---
  - type: web
    name: finrisk-landing
    runtime: static
    rootDir: landing
    buildCommand: npm ci && npm run build
    staticPublishPath: dist
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

- [ ] **Step 2: Check the file parses and has the expected shape**

Run:

```bash
python3 -I - <<'E'
import yaml
b = yaml.safe_load(open("render.yaml"))
names = [s["name"] for s in b["services"]] + [d["name"] for d in b["databases"]]
assert names == ["finrisk-backend", "finrisk-rag", "finrisk-landing", "finrisk-db"], names
assert all(s.get("region", "oregon") == "oregon" for s in b["services"] if s["type"] != "web" or s["runtime"] != "static")
print("render.yaml ok:", names)
E
```

Expected: `render.yaml ok: ['finrisk-backend', 'finrisk-rag', 'finrisk-landing', 'finrisk-db']`. (If `python3` lacks PyYAML, `pip install pyyaml` into a throwaway venv; do not install it system-wide.) If the Render CLI is installed, also run `render blueprints validate render.yaml`.

- [ ] **Step 3: Commit, then deploy (manual: needs your Render account)**

```bash
git add render.yaml
git commit -m "build: Render Blueprint for backend, RAG, database and landing"
```

Push the branch, then in the Render dashboard choose New, then Blueprint, pick the repository and branch, and fill the two `sync: false` secrets (`FMP_API_KEY`, `GEMINI_API_KEY`) when prompted. Creating the account, the services and the paid plans is yours to approve; nothing here does it for you.

After the first deploy finishes:

```bash
curl -sf https://finrisk-backend.onrender.com/actuator/health
```

Expected: `{"status":"UP"...}`. (Your URL may differ if the name is taken.) In the backend's deploy log, check that Flyway reports `Successfully applied 4 migrations` and that no `dev` seed ran. If the build log shows it could not find the Dockerfile, the `dockerfilePath`/`dockerContext` pair is the thing to adjust; both are repo-root relative in this file.

Cost and behaviour to expect: the RAG service needs the 2 GB plan to load its models, which is the largest line item; the first request after a deploy is slow while models load; the Postgres plan is paid (Render's free Postgres expires after 30 days).

---

### Task 14: Retire the old services, vendor `hybrid-rag`, update the docs

**Files:**
- Modify: repo index (remove the gitlinks for `risk-management-ms`, `sector-valuation-ms`, `hybrid-rag`)
- Create: `.gitignore` (repo root), possibly `hybrid-rag/.gitignore`
- Modify: `README.md`, `.claude/CLAUDE.md` (Tier 3 only), `tasks/todo.md`

**Interfaces:**
- Consumes: everything above; `~/finrisk-archive/` as the place the old repos are moved to (outside the project).
- Produces: a main repo that contains the whole product as plain files.

- [ ] **Step 1: Record what is being retired, then move the old repos out of the tree**

Nothing is deleted. The nested repos keep their full history in the archive.

```bash
cd "$(git rev-parse --show-toplevel)"
for d in risk-management-ms sector-valuation-ms hybrid-rag; do
  echo "$d: $(git -C $d branch --show-current) $(git -C $d rev-parse --short HEAD)"
  git -C $d status --short | grep -v 'target/' | head -5
done
```

Expected: `risk-management-ms` on `feature/portfolio-analytics-extras`, `sector-valuation-ms` on `feature/ddm-lynch-fair-value`, `hybrid-rag` on `main`. Any uncommitted lines printed (for example `openapi.yaml` in the risk repo) are not part of `backend/`; commit or keep them in the archive as you prefer before moving.

```bash
mkdir -p ~/finrisk-archive
git rm --cached risk-management-ms sector-valuation-ms hybrid-rag
mv risk-management-ms sector-valuation-ms ~/finrisk-archive/
mv hybrid-rag/.git ~/finrisk-archive/hybrid-rag.git
```

- [ ] **Step 2: Ignore what must never be committed, then add `hybrid-rag` as plain files**

Root `.gitignore`:

```gitignore
.env
node_modules/
backend/**/target/
.idea/
*.iml
```

Make sure `hybrid-rag/.gitignore` exists and contains these lines (create it, or append the missing ones):

```gitignore
venv/
__pycache__/
.pytest_cache/
cache/
.env
```

Then:

```bash
git add .gitignore hybrid-rag
git status --short | grep -E "venv/|__pycache__|\.env$" || echo "nothing unwanted staged"
du -sh hybrid-rag
git commit -m "chore: vendor hybrid-rag into the main repo and drop the service gitlinks"
```

Expected: `nothing unwanted staged`; `du` shows a small folder (a few MB at most; if it shows hundreds of MB, `venv/` was not ignored: fix `hybrid-rag/.gitignore`, run `git rm -r --cached hybrid-rag` and `git add hybrid-rag` again before committing).

- [ ] **Step 3: Rewrite `README.md`**

Replace the whole file with:

````markdown
# FinRisk

Risk-first investment analysis: portfolio risk, intrinsic valuation and market data in one backend, plus a document Q&A service.

| Part | Stack | Port | Folder |
|------|-------|------|--------|
| Backend (Data, Valuation, Portfolio, Risk) | Java 21, Spring Boot 3.3, PostgreSQL, Flyway | 8080 | [`backend/`](./backend/) |
| RAG (document Q&A) | Python 3.11, FastAPI, FAISS, BM25 | 8000 | [`hybrid-rag/`](./hybrid-rag/) |
| Landing page | React, Tailwind, Vite | 5173 (dev) | [`landing/`](./landing/) |

## How the backend is organised

One Spring Boot application built from four bounded contexts (Maven modules under `backend/`):

- **Data** (`marketdata-api`, `marketdata`): the `MarketData` interface and one adapter per vendor. FMP is tried first, Yahoo second. Results are cached in memory.
- **Valuation** (`valuation`): DCF, dividend discount, Peter Lynch fair value, peer comparison. Sees market data only through `MarketData`.
- **Portfolio and Risk** (`risk`): users, accounts, assets, trades, and the risk analytics (risk score, beta, alpha, correlation, drawdown, downside, sector exposure, diversification, ETF look-through and overlap). Sees market data only through `MarketData`.
- **App** (`app`): wiring, configuration, the full-stack test and the architecture rules.

Valuation and Risk cannot import the vendor adapters (Maven) and cannot import each other's internals (ArchUnit).

## Run it locally

```bash
cp .env.example .env        # then set DB_PASSWORD (and FMP_API_KEY if you have one)
docker compose up --build
```

- Backend: http://localhost:8080 (health: `/actuator/health`). `BACKEND_PROFILE=dev` loads seed data: 10 users, 6 assets, 60 days of prices; account 1 holds AAPL and SPY.
- RAG: http://localhost:8000/health

Without Docker: start Postgres, then `cd backend && mvn -pl app -am spring-boot:run -Dspring-boot.run.profiles=dev` (reads `DB_*` and `FMP_API_KEY` from the environment).

## Tests

```bash
cd backend
mvn test        # unit tests, no Docker
mvn verify      # + integration tests on a real Postgres (needs Docker)
cd ../hybrid-rag && pytest
```

## API

Risk (per account): `GET /api/v1/accounts/{id}/{portfolio,profit-loss,risk,beta,alpha,sector-exposure,diversification,correlation,drawdown,downside,etf-look-through,etf-overlap}`.
Accounts, assets and trades: `/api/v1/users`, `/api/v1/accounts`, `/api/v1/assets`, `/api/v1/transactions/{buy,sell}`.
Valuation: `POST /api/v1/valuation/{dcf,ddm,lynch,analyze,compare}`.
The files in `docs/openapi/` describe the old separate services and are out of date.

## Market data sources

Order is set by `MARKETDATA_SOURCES` (default `fmp,yahoo`). If a source fails, is rate limited or has no data, the next one is tried. FMP is skipped when `FMP_API_KEY` is empty. **Yahoo is an unofficial fallback**: it uses Yahoo's public web endpoints, which can change or block requests without notice, and Yahoo's data is not cleared for redistribution. Set `YAHOO_ENABLED=false` to turn it off. Yahoo has no peer lists, so `analyze` and `compare` need FMP.

## Deploy on Render

Render does not run docker-compose files. [`render.yaml`](./render.yaml) is the Blueprint: a Postgres database, the backend (Docker), the RAG service (Docker, private) and the landing page (static). In the Render dashboard choose New, Blueprint, select this repo, and set `FMP_API_KEY` and `GEMINI_API_KEY` when asked. The schema is applied automatically on start (Flyway); production does not load seed data.
````

- [ ] **Step 4: Update `.claude/CLAUDE.md` (Tier 3 only; leave Tier 1 and Tier 2 as they are)**

Replace everything from the line `## TIER 3 — PROJECT FACTS` to the end of the file with:

````markdown
## TIER 3 — PROJECT FACTS

One Java backend plus one Python service, in a single repo (plain files, no gitlinks).

| Part | Stack | Port |
|------|-------|------|
| `backend/` (Data, Valuation, Portfolio, Risk) | Java 21, Spring Boot 3.3, PostgreSQL 16, Flyway, Maven multi-module | 8080 |
| `hybrid-rag/` | Python 3.11, FastAPI, LangChain/LangGraph, FAISS + BM25 | 8000 |
| `landing/` | Vite, React 19, Tailwind 4 | 5173 (dev) |

The old `risk-management-ms` and `sector-valuation-ms` repos live in `~/finrisk-archive/`; do not recreate them.

### Commands

```bash
# whole stack
cp .env.example .env && docker compose up --build

# backend (from backend/)
mvn test                 # unit tests, no Docker
mvn verify               # + *IT tests on Testcontainers Postgres (needs Docker)
mvn -pl valuation -am test   # one module (and what it depends on)

# hybrid-rag
uvicorn src.api.app:app --reload --port 8000
pytest

# landing (from landing/)
npm run dev
npm run build
```

### Backend architecture (`backend/`)
- Modules: `marketdata-api` (the `MarketData` port), `marketdata` (FMP and Yahoo adapters, failover, cache), `valuation`, `risk` (Portfolio + Risk contexts), `app` (Spring Boot entry point, config, ArchUnit rules, full-stack test).
- `valuation` and `risk` depend on `marketdata-api` only. Never import from `com.finrisk.marketdata.fmp`, `.yahoo` or `.source` in them. To add a data source, add a `MarketDataSource` adapter in `marketdata` and list it in `MarketDataConfiguration`.
- `MarketData` never throws: it returns an empty list, an empty `Optional`, or `CompanyProfile.unknown(...)`. Sources throw `SourceUnavailableException` and the failover moves to the next source. Never put URLs or API keys in exception messages or logs.
- Packages in `risk`: `shared` (JDBC helpers, `Page`), `portfolio.{domain,application,infrastructure,web}`, `risk.{domain,application,web}`. `risk` may use only `portfolio.domain`. ArchUnit enforces this; do not weaken a rule to pass.
- Persistence is plain JDBC (`shared/Db`) on a Spring-managed DataSource, not JPA. Schema changes are new Flyway files in `risk/src/main/resources/db/migration` (never edit an applied one). Seed data is `db/dev` and loads only with the `dev` profile. Trades and cash movements are atomic Java in `PostgresTransactionRepository` and `PostgresAccountRepository.adjustCash`; there are no stored procedures.
- Tests: Mockito unit tests run on `mvn test`. `*IT` classes need Docker and run on `mvn verify`. No test may touch the network; fake `HttpFetcher` or `MarketData`.
- Config comes from env vars: `PORT`, `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`, `MARKETDATA_SOURCES`, `FMP_API_KEY`, `YAHOO_ENABLED`, `SPRING_PROFILES_ACTIVE`.
- Yahoo is an unofficial fallback and may break without notice.

### hybrid-rag
- `src/api/app.py` builds the retriever, the LLM and the LangGraph pipeline once at startup and stores them on `app.state`. Routes: `POST /ingest`, `POST /query`, `GET /health`.
- All config is read from env vars in `src/core/config.py`. `LLM_PROVIDER` is `ollama` or `gemini` (only `gemini` works on Render). `RAG_MODE` is `hybrid`, `semantic` or `lexical`.
- Embeddings and the cross-encoder reranker run locally (sentence-transformers). Indexes are saved to `CACHE_DIR`.

### Deploy
- `render.yaml` is the Render Blueprint (Render cannot run docker-compose). `docker-compose.yml` is for local runs only. Secrets are `sync: false` and set in the Render dashboard.

### Specs & plans
- `docs/superpowers/plans/2026-11-19-java-modular-monolith.md`: the refactor this layout comes from.
- `docs/superpowers/specs/2026-07-04-production-readiness-design.md`: older spec for the three-service layout; the Java parts are superseded by the monolith.
````

- [ ] **Step 5: Mark the older plan superseded in `tasks/todo.md`**

Append to `tasks/todo.md`:

```markdown

---

# Update: the `data-ms` plan above is superseded

The separate Node `data-ms` service is replaced by the Data context inside the Java monolith (`backend/marketdata-api` and `backend/marketdata`), with FMP and Yahoo adapters behind the `MarketData` interface. The five free sources (EDGAR, FRED, World Bank, GDELT, Comtrade) are still wanted; they become more `MarketDataSource` adapters or new contexts later. See `docs/superpowers/plans/2026-11-19-java-modular-monolith.md`.
```

- [ ] **Step 6: Final verification**

```bash
cd backend && mvn -B verify          # every module, unit and integration tests (Docker needed)
cd .. && docker compose up --build -d && sleep 20 && curl -sf localhost:8080/actuator/health && docker compose down -v
grep -rn "risk-management-ms\|sector-valuation-ms" README.md .claude/CLAUDE.md render.yaml docker-compose.yml || echo "no stale references"
```

Expected: `BUILD SUCCESS`. Per module: `marketdata-api` 6, `marketdata` 40 (FMP 13, Yahoo 10, failover 9, cache 5, config 3), `valuation` 43 (domain 19, service 17, web 7), `risk` 100 unit tests plus `TradeExecutionIT` 6, `app` `FullStackIT` 17 and `ArchitectureTest` 6 (218 in total). The health call prints `{"status":"UP"...}`. The grep prints no hits except the deliberate archive-folder sentence in `CLAUDE.md`.

- [ ] **Step 7: Commit**

```bash
git add README.md .claude/CLAUDE.md tasks/todo.md docs/superpowers/plans/2026-11-19-java-modular-monolith.md
git commit -m "docs: README, CLAUDE.md and todo for the Java monolith layout"
```

---

## Requirement coverage

| Your requirement | Where it is delivered |
|---|---|
| Fewer microservices: Risk, Valuation and Data in one codebase | One Maven multi-module Spring Boot app (`backend/`); Tasks 1-11 |
| All in Java, OOP with DDD | Valuation rewritten as domain models plus an application service (Tasks 5-7); Portfolio and Risk restructured into domain, application, infrastructure and web layers with ports and adapters (Tasks 8-9); layer rules enforced (Task 11) |
| Valuation and Risk decoupled from FMP and rely on Data | They depend only on `marketdata-api`; compile-time via Maven, plus ArchUnit (Tasks 1, 8, 11) |
| Data is an interface with format adapters | `MarketData` port (Task 1); `FmpSource` + `FmpMapper` and `YahooSource` + `YahooMapper` translate each vendor's format (Tasks 2-3) |
| yfinance in case FMP is not working | `YahooSource` as the second source behind `FailoverMarketData` (Tasks 3-4); the caveat is in Decisions item 4 |
| RAG is the only additional microservice | `hybrid-rag` kept as is, containerised and vendored (Tasks 12-14) |
| Deployment on Render as a docker-compose package | `docker-compose.yml` for local, `render.yaml` Blueprint for Render, because Render cannot run compose (Tasks 12-13; Decisions item 1) |
| Replace SQL Server | PostgreSQL, Flyway, stored procedures turned into transactional Java; the deposit/withdraw race fixed on the way (Task 9) |

Not covered, on purpose: new data sources (EDGAR, FRED and the rest), stress testing, fundamentals, and any change to `hybrid-rag` code.
