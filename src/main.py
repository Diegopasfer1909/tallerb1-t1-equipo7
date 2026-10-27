"""Ejemplo de uso: report, gráficos y Monte Carlo de una cartera.

    python src/main.py                                             → cartera de ejemplo
    python src/main.py SAN.MC=0.5 AAPL=0.3 ITX.MC=0.2 --rebalanceo monthly --benchmark ^IBEX
                       --fecha-inicio 2022-01-01 --fecha-fin 2025-12-31

Resultado en informe/report.md, informe/graficos.md e informe/graficos/.
"""
import argparse
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")       # sin ventanas: los gráficos se guardan en disco

from toolkit import Cartera  # noqa: E402

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # la consola de Windows no imprime iconos ni tildes
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Report de una cartera de acciones.")
    parser.add_argument("pesos", nargs="*", default=["SAN.MC=0.4", "ITX.MC=0.3", "AAPL=0.3"],
                        help="TICKER=PESO; los pesos deben sumar 1")
    parser.add_argument("--rebalanceo", choices=["monthly", "none"], default="monthly")
    parser.add_argument("--benchmark", default="^STOXX50E", help="índice de referencia: ^STOXX50E, ^IBEX, ^GSPC...")
    parser.add_argument("--fecha-inicio", default=None, help="AAAA-MM-DD; por defecto, hace 5 años")
    parser.add_argument("--fecha-fin", default=None, help="AAAA-MM-DD; por defecto, hoy")
    parser.add_argument("--capital", type=float, default=10_000, help="capital inicial en euros")
    args = parser.parse_args()

    activos = [p.split("=")[0] for p in args.pesos]
    pesos = [float(p.split("=")[1]) for p in args.pesos]
    os.chdir(Path(__file__).resolve().parents[1])     # el informe se guarda en la raíz del repositorio

    try:
        cartera = Cartera(activos, pesos, rebalanceo=args.rebalanceo, benchmark=args.benchmark,
                          fecha_inicio=args.fecha_inicio, fecha_fin=args.fecha_fin,
                          capital_inicial=args.capital)
    except Exception as error:
        sys.exit(f"Error: {error}")

    cartera.montecarlo(n_simulaciones=10_000, horizonte=252)
    report = cartera.report()
    graficos = cartera.plots_report()

    print(cartera.report(["resumen", "advertencias"], graficos=False, ruta=None))
    print(f"\nReport:   {report.archivo}\nGráficos: {graficos.archivo}")
