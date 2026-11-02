# Arquitectura

GitHub dibuja estos diagramas directamente (Mermaid). Para editarlos o exportarlos a imagen: <https://mermaid.live>.

## 1. Capas y dependencias

El usuario trabaja con la consola (`src/main.py`) o con `Portfolio`. La capa de **proveedores** es la única que se conecta a internet, y la carga de datos la usa a través del contrato `PriceProvider`, nunca de una API concreta: cambiar de Yahoo a Alpha Vantage (o añadir otra API) no toca el resto del sistema.

```mermaid
flowchart TB
    usuario(["Usuario"])
    main["main.py · --assets --report --simulate --benchmark..."]
    loaders["portfolio_loader · market_loader"]

    subgraph providers["providers · se conectan a las APIs"]
        direction LR
        contrato["PriceProvider (contrato)"]
        yahoo[YahooFinanceAPI]
        av[AlphaVantageAPI]
        fred["FredAPI (con clave) · EcbAPI"]
    end

    subgraph models["models · DataClasses"]
        direction LR
        portfolio["Portfolio<br/>.analyze() · .monte_carlo() · .report() · .plots_report()"]
        asset["Asset · PriceHistory · AssetProfile"]
        refs["MarketReferences · EconomicIndicator · FxRates"]
    end

    subgraph calc["analysis y simulation · solo pandas y numpy"]
        direction LR
        an["PortfolioAnalysis · metrics · MarketContext · warnings"]
        sim["simulate() · SimulationResult"]
    end

    subgraph reporting["reporting"]
        direction LR
        rep["report · 10 secciones en Markdown"]
        plots["plots · 12 gráficos"]
        exp["export · informes/AAAA-MM-DD_HH-MM-SS/"]
    end

    apis[("Yahoo Finance · Alpha Vantage · FRED · BCE")]

    usuario --> main --> loaders
    usuario --> portfolio
    loaders --> contrato
    loaders --> fred
    contrato --> yahoo & av
    yahoo & av & fred --> apis
    loaders -- "crean" --> asset & refs & portfolio
    portfolio --> an & sim
    an --> rep & plots
    sim --> rep & plots
    rep & plots --> exp
```

## 2. Diagrama de clases (UML)

```mermaid
classDiagram
    direction TB

    class PriceProvider {
        <<protocol>>
        +get_prices(symbol, start, end, adjusted) PriceHistory
    }
    class YahooFinanceAPI
    class AlphaVantageAPI {
        +api_key: str
    }
    class FredAPI {
        +get_series(series_id, start, end) EconomicIndicator
    }
    class EcbAPI {
        +get_series(series_id, start, end) EconomicIndicator
    }
    PriceProvider <|.. YahooFinanceAPI
    PriceProvider <|.. AlphaVantageAPI

    class AssetProfile {
        <<dataclass>>
        +currency: str
        +name: str
        +asset_type: str
        +sector: str
        +country: str
    }
    class PriceHistory {
        <<dataclass>>
        +symbol: str
        +source: str
        +prices: DataFrame
        +profile: AssetProfile
        +price_basis: str
        +mean: Series
        +std: Series
        +closing_prices(column) Series
        +returns(log, column) Series
    }
    class Asset {
        <<dataclass>>
        +history: PriceHistory
        +currency: str
        +asset_type: str
        +equity_share: float
        +monte_carlo(settings) SimulationResult
    }
    class EconomicIndicator {
        <<dataclass>>
        +series_id: str
        +source: str
        +values: Series
        +units: str
        +frequency: str
        +as_of(dates, max_age_days) Series
    }
    class FxRates {
        <<dataclass>>
        +rates: tuple
        +convert(prices, source, target) Series
    }
    class MarketReferences {
        <<dataclass>>
        +benchmark: PriceHistory
        +inflation: EconomicIndicator
        +risk_free_rate: EconomicIndicator
        +vix: EconomicIndicator
        +brent: EconomicIndicator
        +gold: PriceHistory
        +bund_etf: PriceHistory
        +benchmark_fx: FxRates
        +notices: tuple
    }
    class Portfolio {
        <<dataclass>>
        +assets: Sequence
        +target_weights: Series
        +reporting_currency: str
        +fx_rates: FxRates
        +initial_capital: float
        +rebalance: str
        +holdings(price_column) DataFrame
        +analyze(references) PortfolioAnalysis
        +monte_carlo(settings) SimulationResult
        +report(references, simulation, sections, detail) Path
        +plots_report(directory, show) dict
    }
    class SimulationSettings {
        <<dataclass>>
        +steps: int
        +simulations: int
        +seed: int
        +confidence: float
        +expected_returns: float
        +volatilities: float
        +equity_premium: float
        +risk_free_rate: float
    }
    class SimulationResult {
        <<dataclass>>
        +paths: DataFrame
        +assumptions: DataFrame
        +confidence: float
        +summary() Series
        +plot(show, max_paths) Figure
    }
    class MarketContext {
        <<dataclass>>
        +vix_current: float
        +brent_correlation: float
        +gold_correlation: float
        +bund_etf_correlation: float
        +bund_on_worst_days: float
        +fx_effect: Series
    }
    class RiskWarning {
        <<dataclass>>
        +code: str
        +severity: str
        +message: str
        +observed: float
        +threshold: float
    }
    class PortfolioAnalysis {
        <<dataclass>>
        +values: Series
        +metrics: Series
        +holdings: DataFrame
        +correlations: DataFrame
        +market: MarketContext
        +risk_warnings: list
        +notices: list
        +markdown(sections, detail) str
        +report(simulation, sections, detail, directory) Path
        +plots_report(directory, show) dict
    }

    PriceProvider ..> PriceHistory : crea
    FredAPI ..> EconomicIndicator : crea
    EcbAPI ..> EconomicIndicator : crea
    PriceHistory *-- AssetProfile
    Asset *-- PriceHistory
    Portfolio "1" o-- "1..*" Asset : assets
    Portfolio o-- FxRates
    MarketReferences o-- PriceHistory
    MarketReferences o-- EconomicIndicator
    MarketReferences o-- FxRates
    Portfolio ..> SimulationSettings : usa
    Portfolio ..> SimulationResult : crea
    Portfolio ..> MarketReferences : usa
    Portfolio ..> PortfolioAnalysis : crea
    PortfolioAnalysis *-- MarketContext
    PortfolioAnalysis o-- RiskWarning
```

## 3. Flujo de una ejecución

```mermaid
sequenceDiagram
    actor U as Usuario
    participant M as main.py
    participant L as loaders
    participant Y as Yahoo / Alpha Vantage
    participant F as FRED y BCE
    participant P as Portfolio
    participant A as analysis y simulation
    participant R as reporting

    U->>M: --assets --currency --rebalance --capital --benchmark --report
    M->>M: validar opciones antes de descargar
    M->>L: load_portfolio(pesos, proveedor, fechas)
    L->>Y: precios, fichas y tipos de cambio
    L-->>M: Portfolio
    M->>L: load_risk_free_rate(divisa, fin)
    L->>F: último tipo libre de riesgo
    M->>P: monte_carlo(settings, price_column)
    P->>A: simulate()
    A-->>M: SimulationResult
    M->>L: load_references(divisa, fechas, benchmark)
    L->>Y: índice, oro, ETF de Bunds
    L->>F: inflación, tipo libre de riesgo, VIX, Brent
    L-->>M: MarketReferences
    M->>P: analyze(references, price_column)
    P->>A: métricas, contexto de mercado y advertencias
    A-->>M: PortfolioAnalysis
    M->>R: report(simulation, sections, detail, directory)
    R-->>U: informes/AAAA-MM-DD_HH-MM-SS/ (Markdown y gráficos)
```
