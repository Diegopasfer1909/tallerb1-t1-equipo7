"""Noticias de Google News (RSS) y su sentimiento: pysentimiento en español, FinBERT en inglés.

Los modelos de sentimiento son opcionales (paquetes pesados); sin ellos se descargan los
titulares, pero sin puntuación.
"""
import os
import warnings
from functools import lru_cache
from urllib.parse import quote

import pandas as pd

REGIONES = {"es": "hl=es&gl=ES&ceid=ES:es", "en": "hl=en-US&gl=US&ceid=US:en"}
COLUMNAS = ["ticker", "fecha", "titular", "score"]


class GoogleNews:
    nombre = "Google News RSS"

    def __init__(self, dias: int = 30, max_titulares: int = 50):
        self.dias = dias
        self.max_titulares = max_titulares

    def titulares(self, empresa: str, idioma: str = "es") -> pd.DataFrame:
        import feedparser

        busqueda = quote(f'"{empresa}" when:{self.dias}d')
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={busqueda}&{REGIONES[idioma]}")
        filas = [{"fecha": pd.Timestamp(*e.published_parsed[:6]), "titular": e.title}
                 for e in feed.entries if getattr(e, "published_parsed", None)]
        tabla = pd.DataFrame(filas, columns=["fecha", "titular"])
        return tabla.sort_values("fecha", ascending=False).head(self.max_titulares)

    def descargar(self, empresas: dict[str, tuple[str, str]], fallos: list) -> pd.DataFrame:
        """empresas: {ticker: (nombre a buscar, idioma "es"/"en")}. Los fallos se anotan en `fallos`."""
        tablas = []
        for ticker, (empresa, idioma) in empresas.items():
            try:
                tabla = self.titulares(empresa, idioma)
            except Exception:
                fallos.append(f"Noticias de {ticker}")
                continue
            tabla["score"] = float("nan")
            if not tabla.empty:
                try:
                    tabla["score"] = sentimiento(tabla["titular"].tolist(), idioma)
                except Exception:       # modelo no instalado o sin conexión para bajarlo
                    if "Sentimiento" not in fallos:
                        fallos.append("Sentimiento")
            tablas.append(tabla.assign(ticker=ticker))
        return pd.concat(tablas, ignore_index=True)[COLUMNAS] if tablas else pd.DataFrame(columns=COLUMNAS)


@lru_cache(maxsize=None)
def _modelo(idioma: str):
    # Los modelos de Hugging Face llenan la consola de barras de progreso y avisos.
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    try:
        import datasets
        datasets.disable_progress_bars()
    except ImportError:
        pass
    if idioma == "es":
        from pysentimiento import create_analyzer

        return create_analyzer(task="sentiment", lang="es")

    from transformers import pipeline

    return pipeline("text-classification", model="ProsusAI/finbert", top_k=None)


def sentimiento(titulares: list[str], idioma: str = "es") -> list[float]:
    """P(positivo) − P(negativo) por titular, de −1 a +1."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        modelo = _modelo(idioma)
        if idioma == "es":
            return [p.probas["POS"] - p.probas["NEG"] for p in modelo.predict(titulares)]
        resultados = [{d["label"]: d["score"] for d in r} for r in modelo(titulares)]
    return [r.get("positive", 0) - r.get("negative", 0) for r in resultados]
