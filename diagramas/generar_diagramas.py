"""Láminas UML editables. Ejecutar con Python + Pillow; no consulta proveedores.

Una misma escena genera Excalidraw, SVG y PNG. Mermaid conserva la descripción
semántica en archivos independientes. Las posiciones se diseñan explícitamente.
"""

from __future__ import annotations

import ast
import hashlib
import html
import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
FONT = os.environ.get("DIAGRAM_FONT", "C:/Windows/Fonts/arial.ttf")
INK = "#142D43"
MUTED = "#526779"
EDGE = "#64798B"
PAPER = "#F6F8FB"
LINE = "#D5DFE7"
BLUE = ("#EAF2FF", "#2464AD")
TEAL = ("#E4F5F1", "#087D76")
VIOLET = ("#F0EBFF", "#7052AB")
AMBER = ("#FFF2D9", "#A66810")
SLATE = ("#EDF1F5", "#526779")
RED = ("#FDEDEC", "#B34545")


def font(size):
    return ImageFont.truetype(FONT, round(size))


class Diagram:
    def __init__(self, name, width, height, number, title, subtitle):
        self.name, self.width, self.height = name, width, height
        self.elements = []
        self.rect(0, 0, width, height, PAPER, PAPER)
        self.rect(0, 0, 16, height, TEAL[1], TEAL[1])
        self.text(72, 35, "MIAX  /  B1–T1  /  EQUIPO 7", 19, TEAL[1])
        self.text(72, 76, title, 46)
        self.text(74, 140, subtitle, 23, MUTED)
        self.rect(width - 146, 38, 74, 74, INK, INK, rounded=True)
        self.text(width - 109, 57, number, 32, "#FFFFFF", center=True)

    def base(self, kind, x, y, w, h, fill="transparent", stroke=INK, dash=False):
        i = len(self.elements) + 1
        e = dict(
            id=f"{self.name}-{i}",
            type=kind,
            x=x,
            y=y,
            width=w,
            height=h,
            angle=0,
            strokeColor=stroke,
            backgroundColor=fill,
            fillStyle="solid",
            strokeWidth=2,
            strokeStyle="dashed" if dash else "solid",
            roughness=0,
            opacity=100,
            groupIds=[],
            frameId=None,
            roundness=None,
            seed=i * 971,
            version=1,
            versionNonce=i * 103,
            isDeleted=False,
            boundElements=[],
            updated=1793443200000,
            link=None,
            locked=False,
        )
        self.elements.append(e)
        return e

    def rect(self, x, y, w, h, fill="#FFFFFF", stroke=LINE, rounded=False, dash=False):
        e = self.base("rectangle", x, y, w, h, fill, stroke, dash)
        if rounded:
            e["roundness"] = {"type": 3}
        return e

    def text(self, x, y, value, size=23, color=INK, center=False):
        lines = value.splitlines() or [""]
        w = max(font(size).getlength(s) for s in lines) + 2
        h = len(lines) * size * 1.28
        e = self.base("text", x - w / 2 if center else x, y, w, h, stroke=color)
        e.update(
            text=value,
            originalText=value,
            fontSize=size,
            fontFamily=2,
            textAlign="center" if center else "left",
            verticalAlign="top",
            containerId=None,
            autoResize=True,
            lineHeight=1.28,
        )
        return e

    def line(self, points, arrow=True, dash=False, color=EDGE):
        x, y = points[0]
        e = self.base(
            "arrow" if arrow else "line",
            x,
            y,
            max(a for a, _ in points) - min(a for a, _ in points),
            max(b for _, b in points) - min(b for _, b in points),
            stroke=color,
            dash=dash,
        )
        e.update(
            points=[[a - x, b - y] for a, b in points],
            lastCommittedPoint=None,
            startBinding=None,
            endBinding=None,
            startArrowhead=None,
            endArrowhead="arrow" if arrow else None,
        )
        return e

    def label(self, x, y, value, size=20, color=MUTED, bg=PAPER, center=False):
        w = max(font(size).getlength(s) for s in value.splitlines()) + 14
        h = len(value.splitlines()) * size * 1.28 + 8
        self.rect(x - w / 2 if center else x - 6, y - 3, w, h, bg, bg, rounded=True)
        return self.text(x, y, value, size, color, center)

    def group(self, start, name):
        for e in self.elements[start:]:
            e["groupIds"] = [name]

    def card(self, x, y, w, h, title, body, palette=SLATE, tag=None, size=23):
        start = len(self.elements)
        box = self.rect(x, y, w, h, "#FFFFFF", LINE, rounded=True)
        self.rect(x + 1, y + 1, 7, h - 2, palette[1], palette[1], rounded=True)
        yy = y + 22
        if tag:
            self.text(x + 24, yy, tag, 17, palette[1])
            yy += 30
        title_e = self.text(x + 24, yy, title, 28, palette[1])
        assert title_e["width"] <= w - 40, title
        if body:
            e = self.text(x + 24, yy + 44, body, size, MUTED)
            assert e["width"] <= w - 40, (title, body, e["width"], w)
            # La última línea no necesita el interlineado inferior para caber en la tarjeta.
            bottom = e["y"] + e["height"] - size * 0.28
            assert bottom <= y + h - 6, (title, bottom, y + h)
        self.group(start, box["id"] + "-group")
        return box

    def cls(self, x, y, w, name, attrs, methods, palette=TEAL, stereotype="dataclass · frozen"):
        start = len(self.elements)
        ah = max(1, len(attrs.splitlines())) * 28 + 24
        mh = max(1, len(methods.splitlines())) * 28 + 24
        h = 83 + ah + mh
        box = self.rect(x, y, w, h, "#FFFFFF", palette[1])
        self.rect(x + 1, y + 1, w - 2, 80, palette[0], palette[0])
        self.text(x + 20, y + 14, f"«{stereotype}»", 17, palette[1])
        title_e = self.text(x + 20, y + 41, name, 29, palette[1])
        assert title_e["width"] <= w - 35, name
        self.line([(x, y + 83), (x + w, y + 83)], False, color=palette[1])
        self.line([(x, y + 83 + ah), (x + w, y + 83 + ah)], False, color=LINE)
        for yy, value in ((y + 94, attrs), (y + 94 + ah, methods)):
            e = self.text(x + 20, yy, value or "—", 22)
            assert e["width"] <= w - 35, (name, value, e["width"], w)
        self.group(start, box["id"] + "-group")
        return box

    def uml(self, pts, relation="association", color=EDGE):
        pts = list(pts)
        first, second = pts[0], pts[1]
        if relation in ("aggregate", "compose"):
            dx, dy = second[0] - first[0], second[1] - first[1]
            n = math.hypot(dx, dy)
            ux, uy = dx / n, dy / n
            p = (first[0] + 24 * ux, first[1] + 24 * uy)
            a = (first[0] + 12 * ux - 8 * uy, first[1] + 12 * uy + 8 * ux)
            b = (first[0] + 12 * ux + 8 * uy, first[1] + 12 * uy - 8 * ux)
            diamond = self.line([first, a, p, b, first], False, color=color)
            diamond["backgroundColor"] = color if relation == "compose" else "#FFFFFF"
            pts[0] = p
        if relation in ("realize", "inherit"):
            tip, prev = pts[-1], pts[-2]
            dx, dy = prev[0] - tip[0], prev[1] - tip[1]
            n = math.hypot(dx, dy)
            ux, uy = dx / n, dy / n
            base = (tip[0] + 22 * ux, tip[1] + 22 * uy)
            self.line(pts[:-1] + [base], False, relation == "realize", color)
            triangle = self.line(
                [
                    tip,
                    (base[0] - 11 * uy, base[1] + 11 * ux),
                    (base[0] + 11 * uy, base[1] - 11 * ux),
                    tip,
                ],
                False,
                color=color,
            )
            triangle["backgroundColor"] = "#FFFFFF"
        else:
            self.line(pts, True, relation == "dependency", color)

    def decision(self, cx, cy, text, w=230, h=100):
        e = self.base("diamond", cx - w / 2, cy - h / 2, w, h, AMBER[0], AMBER[1])
        lines = len(text.splitlines())
        self.text(cx, cy - lines * 21 * 1.28 / 2, text, 21, INK, True)
        return e

    def dot(self, cx, cy, final=False):
        if final:
            self.base("ellipse", cx - 17, cy - 17, 34, 34, "#FFFFFF", INK)
        self.base("ellipse", cx - 10, cy - 10, 20, 20, INK, INK)

    def footer(self, note):
        y = self.height - 90
        self.line([(72, y), (self.width - 72, y)], False, color=LINE)
        self.text(74, y + 19, note, 19, MUTED)
        self.text(self.width - 72, y + 48, "", 1)

    def save(self):
        ids = {e["id"] for e in self.elements}
        assert len(ids) == len(self.elements)
        for e in self.elements:
            if e["type"] in ("line", "arrow"):
                points = [(e["x"] + p[0], e["y"] + p[1]) for p in e["points"]]
                assert all(0 <= x <= self.width and 0 <= y <= self.height for x, y in points), e
            else:
                assert 0 <= e["x"] and 0 <= e["y"], e
                assert e["x"] + e["width"] <= self.width + 1, e
                assert e["y"] + e["height"] <= self.height + 1, e
        data = dict(
            type="excalidraw",
            version=2,
            source="https://excalidraw.com",
            elements=self.elements,
            appState=dict(viewBackgroundColor=PAPER, gridSize=None),
            files={},
        )
        (OUT / f"{self.name}.excalidraw").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        assert len(
            json.loads((OUT / f"{self.name}.excalidraw").read_text(encoding="utf-8"))["elements"]
        ) == len(ids)
        self.render()
        ElementTree.parse(OUT / f"{self.name}.svg")
        with Image.open(OUT / f"{self.name}.png") as im:
            im.verify()
        return {"name": self.name, "elements": len(ids), "size": [self.width, self.height]}

    def render(self):
        im = Image.new("RGB", (self.width, self.height), PAPER)
        draw = ImageDraw.Draw(im)
        svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}" role="img">',
            f"<title>{html.escape(self.name)}</title>",
            "<desc>Arquitectura de tallerb1-t1-equipo7. Fuente editable Excalidraw y alternativa Mermaid junto a esta imagen.</desc>",
        ]
        for e in self.elements:
            x, y, w, h = [e[k] for k in ("x", "y", "width", "height")]
            color, fill = e["strokeColor"], e["backgroundColor"]
            f = None if fill == "transparent" else fill
            dashed = e["strokeStyle"] == "dashed"
            dash = ' stroke-dasharray="9 7"' if dashed else ""
            style = f'fill="{fill if f else "none"}" stroke="{color}" stroke-width="2" stroke-linejoin="round"{dash}'
            if e["type"] == "text":
                size = e["fontSize"]
                for i, s in enumerate(e["text"].splitlines()):
                    yy = y + i * size * 1.28
                    xx = x + (w - font(size).getlength(s)) / 2 if e["textAlign"] == "center" else x
                    draw.text((xx, yy), s, font=font(size), fill=color, anchor="lt")
                    svg.append(
                        f'<text x="{xx}" y="{yy + size * 0.92}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" fill="{color}">{html.escape(s)}</text>'
                    )
            elif e["type"] == "rectangle":
                r = 16 if e["roundness"] else 0
                draw.rounded_rectangle(
                    (x, y, x + w, y + h), radius=r, fill=f, outline=color, width=2
                )
                svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" {style}/>')
            elif e["type"] == "ellipse":
                draw.ellipse((x, y, x + w, y + h), fill=f, outline=color, width=2)
                svg.append(
                    f'<ellipse cx="{x + w / 2}" cy="{y + h / 2}" rx="{w / 2}" ry="{h / 2}" {style}/>'
                )
            elif e["type"] == "diamond":
                pts = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
                draw.polygon(pts, fill=f, outline=color, width=2)
                svg.append(
                    '<polygon points="' + " ".join(f"{a},{b}" for a, b in pts) + f'" {style}/>'
                )
            else:
                pts = [(x + a, y + b) for a, b in e["points"]]
                if f:
                    draw.polygon(pts, fill=f)
                for p, q in zip(pts, pts[1:], strict=False):
                    length = math.dist(p, q)
                    if dashed and length:
                        for v in range(0, math.ceil(length), 16):
                            t, u = v / length, min(v + 9, length) / length
                            draw.line(
                                [
                                    (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t),
                                    (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u),
                                ],
                                fill=color,
                                width=2,
                            )
                    else:
                        draw.line([p, q], fill=color, width=2)
                svg.append(
                    '<polyline points="' + " ".join(f"{a},{b}" for a, b in pts) + f'" {style}/>'
                )
                if e.get("endArrowhead"):
                    tip, prev = pts[-1], pts[-2]
                    angle = math.atan2(tip[1] - prev[1], tip[0] - prev[0])
                    head = [
                        (
                            tip[0] - 15 * math.cos(angle - 0.45),
                            tip[1] - 15 * math.sin(angle - 0.45),
                        ),
                        tip,
                        (
                            tip[0] - 15 * math.cos(angle + 0.45),
                            tip[1] - 15 * math.sin(angle + 0.45),
                        ),
                    ]
                    draw.line(head, fill=color, width=2)
                    svg.append(
                        '<polyline points="'
                        + " ".join(f"{a},{b}" for a, b in head)
                        + f'" fill="none" stroke="{color}" stroke-width="2"/>'
                    )
        svg.append("</svg>")
        (OUT / f"{self.name}.svg").write_text("\n".join(svg), encoding="utf-8")
        im.save(OUT / f"{self.name}.png", optimize=True)


def architecture():
    d = Diagram(
        "01-arquitectura",
        1920,
        1330,
        "01",
        "Arquitectura del sistema",
        "Vista de componentes · responsabilidades, contratos y recorrido de los datos",
    )
    d.card(
        80,
        230,
        420,
        155,
        "Entrada CLI",
        "Argumentos + archivo de pesos\nVariables de entorno",
        SLATE,
        "INTERFAZ",
    )
    d.card(
        680,
        230,
        560,
        155,
        "main + loaders",
        "Cartera, referencias y precios\npara estimar Monte Carlo (5 años)",
        SLATE,
        "COORDINACIÓN",
    )
    d.card(
        1420,
        230,
        420,
        155,
        "API Python",
        "Objetos y proveedores inyectables\nUso directo de la biblioteca",
        SLATE,
        "OTRA ENTRADA",
        22,
    )
    d.line([(500, 307), (680, 307)])
    d.line([(1420, 307), (1240, 307)])
    d.line([(960, 385), (960, 450), (330, 450), (330, 520)], dash=True)
    d.line([(960, 450), (960, 520)], dash=True)
    d.line([(960, 450), (1590, 450), (1590, 520)], dash=True)
    d.label(1010, 433, "coordina llamadas", 19)
    d.card(
        80,
        520,
        500,
        250,
        "providers",
        "Yahoo · Alpha · FRED · BCE\nCumplen los puertos de ports\nHTTP, caché y cuota de Alpha",
        BLUE,
        "ADQUISICIÓN",
    )
    d.card(
        710,
        520,
        500,
        250,
        "models",
        "Portfolio · Asset · PriceHistory\nFxRates · MarketReferences\nValoración, backtest y comisiones",
        TEAL,
        "DOMINIO",
    )
    d.card(
        1340,
        520,
        500,
        250,
        "simulation",
        "SimulationInputs + Settings\nsimulate() → SimulationResult\nGBM · rebalanceo con comisiones",
        VIOLET,
        "ESCENARIOS",
    )
    d.line([(580, 645), (710, 645)], color=TEAL[1])
    d.label(645, 605, "datos", 20, center=True)
    d.line([(1210, 645), (1340, 645)], color=VIOLET[1])
    d.label(1275, 605, "inputs", 20, center=True)
    d.card(
        80,
        920,
        500,
        220,
        "Referencias de mercado",
        "Benchmark · inflación · tipos\nFX del benchmark cuando procede\nAusencias opcionales → Notice",
        BLUE,
        "market_loader",
    )
    d.card(
        710,
        920,
        500,
        220,
        "analysis",
        "Cartera + referencias + simulación\nMétricas y avisos → PortfolioAnalysis",
        TEAL,
        "CÁLCULO",
        22,
    )
    d.card(
        1340,
        920,
        500,
        220,
        "reporting",
        "Resultados → Markdown + PNG\nGráficos en pantalla\nEscritura en disco al exportar",
        AMBER,
        "PRESENTACIÓN Y SALIDA",
    )
    d.card(
        1100,
        810,
        380,
        100,
        "commissions",
        "RebalanceRule · rebalance_step()",
        SLATE,
        size=20,
    )
    d.line([(1160, 770), (1160, 810)], color=SLATE[1])
    d.line([(1420, 770), (1420, 810)], color=SLATE[1])
    d.line([(330, 770), (330, 920)], color=BLUE[1])
    d.label(350, 829, "series normalizadas", 20)
    d.line([(960, 770), (960, 920)], color=TEAL[1])
    d.label(980, 870, "histórico", 20)
    d.line([(1590, 770), (1590, 920)], color=VIOLET[1])
    d.label(1610, 829, "escenarios", 20)
    d.line([(580, 1030), (710, 1030)], color=BLUE[1])
    d.line([(1210, 1030), (1340, 1030)], color=AMBER[1])
    d.text(
        82,
        1190,
        "Puertos en el núcleo  ·  adaptadores creados solo en main  ·  cálculo separado de la descarga",
        25,
        TEAL[1],
    )
    d.footer(
        "Flechas: colaboración / datos, no imports. commissions (backtest y Monte Carlo) y frequency (252 o 365) son transversales: lámina 05."
    )
    return d


def domain():
    d = Diagram(
        "02-modelos-dominio",
        2140,
        1580,
        "02",
        "Modelo de dominio",
        "UML de clases · atributos y operaciones seleccionados · multiplicidad en el extremo de destino",
    )
    asset = d.cls(
        80,
        270,
        470,
        "Asset",
        "history: PriceHistory\ncurrency, asset_type: str",
        "+ symbol / latest_price\n+ simulation_inputs()",
    )
    pf = d.cls(
        820,
        270,
        500,
        "Portfolio",
        "assets: tuple[Asset, ...]\ntarget_weights: Series\nunits: Series | None\n"
        "reporting_currency; rebalance\nrebalance_rule: RebalanceRule",
        "+ from_units() / close_prices()\n+ holdings() / backtest()\n"
        "+ analyze()\n+ monte_carlo(estimation_prices)",
    )
    rule = d.cls(
        740,
        700,
        400,
        "RebalanceRule",
        "commissions: CommissionSchedule\nband; max_order_cost?",
        "+ is_free",
    )
    fx = d.cls(
        1600, 270, 460, "FxRates", "rates: tuple[ExchangeRate, ...]", "+ convert() / combine()"
    )
    ph = d.cls(
        80,
        730,
        470,
        "PriceHistory",
        "symbol; source; price_basis\nprices: DataFrame; profile",
        "+ closing_prices() / returns()\n+ mean / std\n+ returns_mean / returns_std",
    )
    er = d.cls(
        1600,
        680,
        460,
        "ExchangeRate",
        "base_currency; quote_currency\nindicator: EconomicIndicator\nmax_age_days: int",
        "+ on_dates()",
    )
    d.cls(
        80,
        1170,
        470,
        "AssetProfile",
        "currency; name; asset_type\nsector; raw; issue",
        "validación en construcción",
    )
    d.cls(
        820,
        1020,
        500,
        "MarketReferences",
        "benchmark: PriceHistory?\ninflation: EconomicIndicator?\nrisk_free_rate: EconomicIndicator?\n"
        "vix, brent: EconomicIndicator?\ngold, bund_etf: PriceHistory?\n"
        "fx_rates: FxRates\nnotices: tuple[Notice, ...]",
        "—",
    )
    d.cls(
        1600,
        1170,
        460,
        "EconomicIndicator",
        "series_id; source; values\nunits; frequency",
        "+ as_of()\n+ mean / std",
    )
    d.uml([(820, 370), (550, 370)], "aggregate", TEAL[1])
    d.label(685, 328, "assets  1..*", 21, center=True)
    d.uml([(315, asset["y"] + asset["height"]), (315, 730)], color=TEAL[1])
    d.label(337, 625, "history  1", 21)
    d.uml([(315, ph["y"] + ph["height"]), (315, 1170)], color=TEAL[1])
    d.label(337, 1080, "profile  1", 21)
    d.uml([(1320, 370), (1600, 370)], color=TEAL[1])
    d.label(1460, 328, "fx_rates  1", 21, center=True)
    d.uml([(1830, fx["y"] + fx["height"]), (1830, 680)], "aggregate", TEAL[1])
    d.label(1850, 590, "rates  0..*", 21)
    d.uml([(1830, er["y"] + er["height"]), (1830, 1170)], color=TEAL[1])
    d.label(1850, 1035, "indicator  1", 21)
    d.uml([(940, pf["y"] + pf["height"]), (940, rule["y"])], color=TEAL[1])
    d.label(960, 664, "rebalance_rule  1", 21)
    d.uml([(1240, pf["y"] + pf["height"]), (1240, 1020)], "dependency")
    d.label(1260, 800, "parámetro de\nanalyze()", 21)
    d.uml([(820, 1110), (680, 1110), (680, 860), (550, 860)], color=BLUE[1])
    d.label(690, 940, "benchmark\n0..1", 21)
    d.uml(
        [(1320, 1090), (1450, 1090), (1450, 540), (1730, 540), (1730, fx["y"] + fx["height"])],
        color=BLUE[1],
    )
    d.label(1365, 560, "fx_rates  1", 21)
    d.uml([(1320, 1230), (1600, 1230)], color=BLUE[1])
    d.label(1460, 1193, "inflation  0..1", 20, center=True)
    d.uml([(1320, 1320), (1600, 1320)], color=BLUE[1])
    d.label(1460, 1282, "risk_free_rate  0..1", 20, center=True)
    d.footer(
        "Rombo hueco: agregación compartida. Discontinua: dependencia de uso. «frozen» no implica inmutabilidad profunda.\n"
        "RebalanceRule vive en el módulo transversal commissions. vix, brent, gold y bund_etf: asociaciones 0..1 listadas como atributos."
    )
    return d


def dependencies():
    d = Diagram(
        "05-dependencias",
        2040,
        1540,
        "05",
        "Dependencias del código",
        "Vista seleccionada de imports · la flecha apunta al paquete importado · inventario completo en ARQUITECTURA.md",
    )
    d.text(82, 218, "A  /  COORDINACIÓN Y CARGA", 21, BLUE[1])
    d.card(80, 275, 260, 150, "main", "Selecciona y coordina", SLATE, size=21)
    d.card(430, 275, 330, 150, "portfolio_loader", "Construye Portfolio", BLUE, size=21)
    d.card(850, 275, 300, 150, "price_loader", "Lotes, hasta 4 hilos", BLUE, size=21)
    d.card(1240, 275, 330, 150, "market_loader", "FX y referencias", BLUE, size=21)
    d.card(1660, 275, 300, 150, "ports", "Contratos del núcleo", BLUE, size=21)
    # main también importa price_loader (límite de --download-workers): arista omitida.
    for x1, x2 in [(340, 430), (760, 850), (1570, 1660)]:
        d.line([(x1, 350), (x2, 350)], color=BLUE[1])
    d.line([(1000, 275), (1000, 245), (1810, 245), (1810, 275)], color=BLUE[1])
    d.line([(595, 425), (595, 448), (1405, 448), (1405, 425)], color=BLUE[1])
    d.text(
        82,
        478,
        "Los loaders solo importan los puertos (ports); main importa providers y crea los adaptadores.",
        23,
        MUTED,
    )
    d.text(82, 564, "B  /  RELACIONES ENTRE PAQUETES DE LA BIBLIOTECA", 21, TEAL[1])
    d.card(80, 680, 460, 190, "analysis", "Cálculos → PortfolioAnalysis", TEAL, "MÉTRICAS", 22)
    d.card(790, 680, 460, 190, "models", "Datos + valoración histórica", TEAL, "DOMINIO", 22)
    d.card(1500, 680, 460, 190, "providers", "Adaptadores de E/S", BLUE, "FUENTES", 22)
    d.card(
        80, 1110, 460, 190, "reporting", "Texto, gráficos y exportación", AMBER, "PRESENTACIÓN", 22
    )
    d.card(
        790, 1110, 460, 190, "simulation", "Inputs, motor y resultados", VIOLET, "ESCENARIOS", 22
    )
    d.line([(540, 760), (790, 760)], color=TEAL[1])
    d.line([(1500, 760), (1250, 760)], color=BLUE[1])
    d.line([(1020, 870), (1020, 1110)], color=VIOLET[1])
    d.label(1040, 966, "import de módulo", 20)
    d.line([(460, 870), (460, 960), (850, 960), (850, 1110)], color=TEAL[1])
    d.label(610, 922, "analysis → simulation", 20, center=True)
    d.line([(790, 710), (690, 710), (690, 620), (300, 620), (300, 680)], dash=True, color=AMBER[1])
    d.label(500, 601, "analyze()", 20, AMBER[1], center=True)
    d.line(
        [(790, 830), (620, 830), (620, 1055), (440, 1055), (440, 1110)], dash=True, color=AMBER[1]
    )
    d.label(640, 1000, "report()", 20, AMBER[1])
    d.line([(230, 870), (230, 1110)], dash=True, color=AMBER[1])
    d.label(250, 1000, "presentación", 20, AMBER[1])
    d.line([(790, 1205), (540, 1205)], dash=True, color=AMBER[1])
    d.label(665, 1164, "plot()", 20, AMBER[1], center=True)
    # reporting también importa al cargar métricas y avisos y los supuestos de Monte Carlo.
    d.line([(380, 1110), (380, 870)], color=AMBER[1])
    d.label(395, 1000, "import", 20, AMBER[1])
    d.line([(540, 1265), (790, 1265)], color=AMBER[1])
    d.label(665, 1272, "import", 20, AMBER[1], center=True)
    d.card(
        1500,
        980,
        460,
        320,
        "Servicios transversales",
        "constants · errors · validation\ncommissions · frequency · ports\nImports omitidos en este recorte.\n\nTYPE_CHECKING:\nmodels ↔ analysis",
        SLATE,
        "DEPENDENCIAS AUXILIARES",
        22,
    )
    d.text(
        82,
        1380,
        "Continuas: imports al cargar el módulo (ámbar: los de reporting).   Discontinuas ámbar: imports dentro de métodos (4 aristas).",
        24,
    )
    d.footer(
        "El grafo de imports de módulo es acíclico. Los imports diferidos conservan acoplamiento; no equivalen a eliminar la dependencia."
    )
    return d


def activity():
    d = Diagram(
        "06-flujo-cli",
        1900,
        2340,
        "06",
        "Flujo de ejecución de la consola",
        "UML de actividad · camino normal y ramas opcionales · main.py",
    )
    cx = 900
    d.dot(cx, 230)
    d.card(
        640,
        290,
        520,
        130,
        "Preparar configuración",
        ".env → parsear → comprobar claves",
        SLATE,
        "ANTES DE LA DESCARGA",
        22,
    )
    d.line([(cx, 240), (cx, 290)])
    d.card(
        640,
        500,
        520,
        185,
        "Cargar y mostrar cartera",
        "Pesos o número de acciones\nproveedor → activos → FX → Portfolio\n"
        "hasta --download-workers a la vez\nImprimir composición y comisiones",
        BLUE,
        size=22,
    )
    d.line([(cx, 420), (cx, 500)])
    d.card(
        1300,
        290,
        510,
        185,
        "Argumentos inválidos",
        "Opción inválida o incompatible\n(comisiones sin --rebalance monthly)\nargparse → salida 2",
        RED,
        "ERROR DE ENTRADA",
        22,
    )
    d.line([(1160, 355), (1300, 355)], dash=True, color=RED[1])
    d.card(
        1300,
        500,
        510,
        240,
        "Errores durante run()",
        "PortfolioError / ProviderError\nOSError → stderr → salida 1\n\nFRED ausente: aviso y continúa.\nAlpha sin clave: se detiene.",
        RED,
        "MANEJADOR DE EXCEPCIONES",
        22,
    )
    # Mismo orden que run(): primero el análisis (referencias incluidas) y después Monte Carlo.
    d.decision(cx, 765, "¿informe\no gráficos?", 270, 130)
    d.line([(cx, 685), (cx, 700)])
    d.card(
        80,
        640,
        430,
        240,
        "Referencias y análisis",
        "--report: load_references()\nbenchmark · FX · FRED / BCE\n"
        "--plots-report: solo --benchmark\nportfolio.analyze()\n→ PortfolioAnalysis",
        TEAL,
        size=21,
    )
    d.line([(765, 765), (510, 765)], color=TEAL[1])
    d.label(640, 725, "sí", 21, center=True)
    d.line([(cx, 830), (cx, 920)], arrow=False)
    d.label(920, 860, "no", 21)
    d.line([(295, 880), (295, 920), (cx, 920)], arrow=False, color=TEAL[1])
    d.decision(cx, 920, "", 32, 32)
    d.decision(cx, 1060, "¿simular?", 220, 110)
    d.line([(cx, 936), (cx, 1005)])
    d.card(
        80,
        960,
        430,
        205,
        "Monte Carlo",
        "Tipo libre de riesgo (FRED / BCE)\nPrecios de estimación (5 años)\n"
        "→ simulate() → resumen\nAviso si hay menos de 3 años",
        VIOLET,
        size=22,
    )
    d.line([(790, 1060), (510, 1060)], color=VIOLET[1])
    d.label(640, 1020, "sí", 21, center=True)
    d.line([(cx, 1115), (cx, 1230)], arrow=False)
    d.label(920, 1150, "no", 21)
    d.line([(295, 1165), (295, 1230), (cx, 1230)], arrow=False, color=VIOLET[1])
    d.decision(cx, 1230, "", 32, 32)
    d.card(
        1300,
        980,
        510,
        165,
        "Condición de simulación",
        "--simulate  o  --report con\nla sección simulation seleccionada.\nEl informe por defecto la incluye.",
        VIOLET,
        size=22,
    )
    d.decision(cx, 1380, "¿informe\no gráficos?", 270, 130)
    d.line([(cx, 1246), (cx, 1315)])
    d.line([(1035, 1380), (1500, 1380), (1500, 1470)])
    d.label(1190, 1341, "no", 21, center=True)
    d.dot(1500, 1487, True)
    d.text(1540, 1473, "salida 0", 23, MUTED)
    d.label(920, 1470, "sí", 21)
    d.card(
        1300,
        1580,
        510,
        250,
        "Orden deliberado",
        "Se analiza antes de simular:\nsi faltan datos, se avisa\nsin simular en balde.\n\n"
        "Sin --report ni --benchmark,\nno se cargan referencias.",
        SLATE,
        size=22,
    )
    d.decision(cx, 1670, "¿--report?", 230, 100)
    d.line([(cx, 1445), (cx, 1620)])
    d.card(
        80,
        1610,
        430,
        130,
        "Guardar informe",
        "analysis.report(simulation)\nMarkdown + imágenes PNG",
        AMBER,
        size=22,
    )
    d.line([(785, 1670), (510, 1670)], color=AMBER[1])
    d.label(640, 1631, "sí", 21, center=True)
    d.line([(cx, 1720), (cx, 1800)], arrow=False)
    d.label(925, 1750, "no", 21)
    d.line([(295, 1740), (295, 1800), (cx, 1800)], arrow=False, color=AMBER[1])
    d.decision(cx, 1800, "", 32, 32)
    d.decision(cx, 1930, "¿--plots-report?", 310, 110)
    d.line([(cx, 1816), (cx, 1875)])
    d.card(80, 1870, 430, 130, "Mostrar gráficos", "Ventanas de Matplotlib", AMBER, size=22)
    d.line([(745, 1930), (510, 1930)], color=AMBER[1])
    d.label(620, 1889, "sí", 21, center=True)
    d.line([(cx, 1985), (cx, 2070)], arrow=False)
    d.label(925, 2010, "no", 21)
    d.line([(295, 2000), (295, 2070), (cx, 2070)], arrow=False, color=AMBER[1])
    d.decision(cx, 2070, "", 32, 32)
    d.line([(cx, 2086), (cx, 2173)])
    d.dot(cx, 2190, True)
    d.text(945, 2175, "salida 0", 23, MUTED)
    d.footer(
        "Rombos: decisión o unión de alternativas. Las ramas no se ejecutan en paralelo. No existe fallback automático entre proveedores."
    )
    return d


def source_inventory():
    paths = sorted((ROOT / "src").rglob("*.py"))
    hashes = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }
    symbols = {}
    for p in paths:
        tree = ast.parse(p.read_text(encoding="utf-8-sig"))
        symbols[p.relative_to(ROOT).as_posix()] = [
            n.name
            for n in tree.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    required = {
        "src/models/currency.py": {"FxRates", "ExchangeRate"},
        "src/models/references.py": {"MarketReferences"},
        "src/models/price_history.py": {"PriceHistory"},
        "src/providers/base.py": {"ApiClient"},
        "src/ports.py": {"PriceProvider", "IndicatorProvider", "ReferenceSources"},
        "src/simulation/monte_carlo.py": {"SimulationInputs", "simulate"},
        "src/providers/ecb.py": {"EcbAPI"},
        "src/frequency.py": {"periods_per_year"},
        "src/commissions.py": {"CommissionSchedule", "RebalanceRule", "rebalance_step"},
        "src/models/backtest.py": {"BacktestResult", "backtest_with_costs"},
    }
    for path, names in required.items():
        assert names <= set(symbols[path]), (path, names)
    return hashes, symbols


def contact_sheet(diagrams):
    w, cellw, cellh = 1800, 850, 680
    rows = (len(diagrams) + 1) // 2
    im = Image.new("RGB", (w, rows * cellh + 140), PAPER)
    draw = ImageDraw.Draw(im)
    draw.text((50, 30), "MIAX · Atlas de arquitectura", font=font(42), fill=INK)
    for i, d in enumerate(diagrams):
        x = 50 + (i % 2) * 900
        y = 110 + (i // 2) * cellh
        preview = Image.open(OUT / f"{d.name}.png").convert("RGB")
        preview.thumbnail((cellw, cellh - 50), Image.Resampling.LANCZOS)
        im.paste(preview, (x + (cellw - preview.width) // 2, y))
        draw.text((x, y + cellh - 43), d.name.replace("-", " "), font=font(23), fill=MUTED)
    im.save(OUT / "vista-general.png", optimize=True)


def main():
    before, symbols = source_inventory()
    diagrams = [f() for f in (architecture, domain, dependencies, activity)]
    checks = [d.save() for d in diagrams]
    contact_sheet(diagrams)
    after, _ = source_inventory()
    if before != after:
        raise RuntimeError("El código cambió durante la generación; revisa y regenera.")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", "src"], cwd=ROOT, text=True
    ).strip()
    basis = "working tree; src differs from HEAD" if dirty else "HEAD; src matches the commit"
    manifest = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        head=revision,
        basis=basis,
        source_sha256=after,
        symbols=symbols,
        diagrams=checks,
        checks=[
            "unique Excalidraw IDs",
            "element bounds",
            "text fits its cards",
            "SVG XML parses",
            "PNG decodes",
            "source stable during render",
        ],
        note="Mermaid files are independent semantic sources. Visual review is separate from structural validation.",
    )
    (OUT / "verificacion.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Generated {len(checks)} diagrams, 3 formats each; {len(after)} source hashes.")


if __name__ == "__main__":
    main()
