import json
from pathlib import Path
import pandas as pd
import yfinance as yf
from dataclasses import dataclass, field

@dataclass
class PriceSeries:
    symbol: str
    source: str
    prices: pd.DataFrame
    mean: pd.Series = field(init=False)
    std: pd.Series = field(init=False)
    info: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.prices = self.prices.copy().sort_index()

        if not isinstance(self.prices.index, pd.DatetimeIndex):
            raise TypeError("Prices must have a DatetimeIndex.")
        if self.prices.empty or self.prices.isna().to_numpy().any():
            raise ValueError("Prices must be nonempty and contain no missing values.")
        if self.prices.index.has_duplicates:
            raise ValueError("Prices must have unique dates.")

        self.mean = self.prices.mean(axis="index", numeric_only=True)
        self.std = self.prices.std(axis="index", numeric_only=True)

class YahooFinanceAPI:
    def get_prices(
        self, symbol: str, start: str, end: str
    ) -> PriceSeries:
        ticker = yf.Ticker(symbol)
        history = ticker.history(
            start=start,
            end=end,
            auto_adjust=True,
        )

        return PriceSeries(
            symbol = symbol,
            source = "yahoo",
            prices = history,
            info = ticker.get_info(),
        )

if __name__ == "__main__":
    api = YahooFinanceAPI()
    price_series = api.get_prices("IBM", "2026-01-01", "2026-12-31")

    # Save beside this script, regardless of the terminal's working directory.
    output_dir = Path(__file__).resolve().parent
    info_json = json.dumps(price_series.info, indent=2, ensure_ascii=False, allow_nan=False)
    prices_json = price_series.prices.rename_axis("Date").reset_index().to_json(
        orient="records", date_format="iso", indent=2, force_ascii=False
    )
    if prices_json is None:
        raise ValueError("Could not serialize the price history.")

    (output_dir / "exampleyahooinfo.json").write_text(info_json + "\n", encoding="utf-8")
    (output_dir / "example.json").write_text(prices_json + "\n", encoding="utf-8")
    print(f"Updated ticker information and prices in {output_dir}")
