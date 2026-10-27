# Arquitectura del toolkit

GitHub dibuja estos diagramas directamente (Mermaid). Para editarlos o exportarlos a imagen: <https://mermaid.live>.

## 1. Capas y dependencias

El usuario solo trabaja con `Cartera`. La capa de **ingesta** es la única que se conecta a internet, y la cartera la usa a través de la interfaz `FuentePrecios`, nunca de una API concreta: cambiar de Yahoo a Alpha Vantage (o añadir otra API) no toca el resto del sistema.

```mermaid
flowchart TB
    usuario(["Usuario"])

    subgraph modelos["modelos · DataClasses"]
        direction LR
        cartera["Cartera<br/>.report() · .plots_report() · .montecarlo()"]
        series["Serie · PriceSeries · MacroSeries"]
        mercado[ContextoMercado]
    end

    subgraph ingesta["ingesta · se conecta a las APIs"]
        direction LR
        fuente["FuentePrecios (interfaz)"]
        yahoo[YahooFinance]
        av[AlphaVantage]
        fred[Fred]
    end

    subgraph analisis["analisis · solo pandas y numpy"]
        direction LR
        pre[preprocesado]
        met[metricas]
        mc[montecarlo]
        adv[advertencias]
    end

    subgraph salida["salida"]
        direction LR
        rep["report.md y graficos.md"]
        graf["graficos (matplotlib)"]
    end

    apis[("Yahoo Finance · Alpha Vantage · FRED")]

    usuario --> cartera
    cartera -- "descarga a través de" --> fuente
    fuente --> yahoo & av
    yahoo & av & fred --> apis
    ingesta -- "devuelve" --> series
    cartera --> series & mercado
    cartera --> pre & met & mc & adv
    cartera --> rep & graf
```

## 2. Diagrama de clases (UML)

```mermaid
classDiagram
    direction TB

    class FuentePrecios {
        <<abstract>>
        +nombre: str
        +ajustado: bool
        #_cierres(symbol, inicio, fin) Series*
        #_metadatos(symbol) dict
        +descargar(symbol, inicio, fin) PriceSeries
        +descargar_varios(symbols, inicio, fin) dict
    }
    class YahooFinance
    class AlphaVantage {
        +api_key: str
    }
    class Fred {
        +descargar(symbol, inicio, fin) MacroSeries
    }
    FuentePrecios <|-- YahooFinance
    FuentePrecios <|-- AlphaVantage

    class Serie {
        <<dataclass>>
        +symbol: str
        +source: str
        +datos: Series
        +nombre: str
        +media: float
        +desviacion: float
        #_calcular_estadisticos()
    }
    class PriceSeries {
        <<dataclass>>
        +divisa: str
        +tipo: str
        +sector: str
        +pais: str
        +ajustado: bool
        +rentabilidades: Series
        +media_anual: float
        +volatilidad_anual: float
        +convertir(tipo_cambio, divisa) PriceSeries
    }
    class MacroSeries {
        <<dataclass>>
        +unidad: str
        +frecuencia: str
        +en_tanto_por_uno() Series
    }
    Serie <|-- PriceSeries
    Serie <|-- MacroSeries

    class ContextoMercado {
        <<dataclass>>
        +indice: PriceSeries
        +bund: MacroSeries
        +inflacion: MacroSeries
        +vix: MacroSeries
        +brent: Serie
        +oro: Serie
        +etf_bund: PriceSeries
        +tipos_cambio: dict
        +fallos: list
    }

    class Cartera {
        <<dataclass>>
        +activos: list
        +pesos: Series
        +rebalanceo: str
        +benchmark: str
        +fecha_inicio: str
        +fecha_fin: str
        +capital_inicial: float
        +fuente: FuentePrecios
        +nombre: str
        +precios: DataFrame
        +valor: Series
        +pesos_actuales: Series
        +simulacion: ResultadoMC
        +report(secciones, umbrales, graficos, ruta) Informe
        +plots_report(graficos, ruta, mostrar) Informe
        +montecarlo(n_simulaciones, horizonte, retorno, volatilidad, activo, por_activos, confianza, semilla, mostrar) ResultadoMC
        +advertencias(umbrales) list
    }

    class ResultadoMC {
        <<dataclass>>
        +trayectorias: ndarray
        +parametros: dict
        +metricas: dict
        +plot(mostrar) Figure
    }

    FuentePrecios ..> PriceSeries : crea
    Fred ..> MacroSeries : crea
    Cartera ..> FuentePrecios : usa
    Cartera "1" o-- "1..*" PriceSeries : activos
    Cartera "1" o-- "1" ContextoMercado : mercado
    ContextoMercado o-- Serie
    Cartera "1" *-- "0..1" ResultadoMC : simulacion
```

## 3. Flujo de una ejecución

```mermaid
sequenceDiagram
    actor U as Usuario
    participant C as Cartera
    participant F as FuentePrecios (Yahoo)
    participant R as Fred
    participant A as analisis
    participant S as salida

    U->>C: Cartera(activos, pesos, rebalanceo, benchmark, fecha_inicio, fecha_fin, capital_inicial)
    C->>F: descargar_varios(activos)  [en paralelo]
    F-->>C: PriceSeries (validadas, con media y desviación)
    C->>F: benchmark, ETF de Bunds, oro
    C->>R: Bund, inflación, VIX, Brent, EUR/USD
    C->>A: validar pesos, alinear calendarios, pasar a EUR, aplicar rebalanceo
    U->>C: montecarlo(n_simulaciones, horizonte, retorno, volatilidad)
    C->>A: simular()
    A-->>C: ResultadoMC (guardado en cartera.simulacion)
    U->>C: report(secciones, umbrales)
    C->>A: métricas y advertencias
    C->>S: report.md (métricas + gráficos)
    S-->>U: report
    U->>C: plots_report(graficos)
    C->>S: gráficos
    S-->>U: graficos.md
```
