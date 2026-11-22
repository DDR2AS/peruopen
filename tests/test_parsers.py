from datetime import date

import pytest

from pipelines.extractors.bcrp import CORE, check_names, parse_batch, parse_period, parse_value
from pipelines.extractors.uit import parse_uit

TODAY = date(2026, 11, 22)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("02.Ene.25", date(2025, 1, 2)),
        ("01.Set.25", date(2025, 9, 1)),  # septiembre diario = "Set"
        ("15.Dic.99", date(1999, 12, 15)),
        ("Sep.2025", date(2025, 9, 1)),  # septiembre mensual = "Sep"
        ("Ene.1992", date(1992, 1, 1)),
    ],
)
def test_parse_period(raw: str, expected: date) -> None:
    assert parse_period(raw, TODAY) == expected


@pytest.mark.parametrize("raw", ["T1.25", "Xyz.2025", "2025", "2025-01-01"])
def test_parse_period_rejects_unknown_format(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_period(raw, TODAY)


def test_parse_value() -> None:
    assert parse_value("3.5415") == pytest.approx(3.5415)
    assert parse_value("n.d.") is None
    assert parse_value(" ") is None
    assert parse_value("abc") is None


def test_parse_batch_maps_columns_and_skips_missing() -> None:
    payload = {
        "config": {"series": [{"name": "a"}, {"name": "b"}]},
        "periods": [
            {"name": "Feb.2025", "values": ["2", "n.d."]},
            {"name": "Ene.2025", "values": ["1", "10"]},
        ],
    }
    rows = sorted(parse_batch(payload, ["A1", "B1"], TODAY))
    assert rows == [
        ("A1", date(2025, 1, 1), 1.0),
        ("A1", date(2025, 2, 1), 2.0),
        ("B1", date(2025, 1, 1), 10.0),
    ]


def test_parse_batch_detects_missing_series() -> None:
    payload = {"config": {"series": [{"name": "a"}]}, "periods": []}
    with pytest.raises(ValueError, match="1 series para 2"):
        list(parse_batch(payload, ["A1", "B1"], TODAY))


def test_core_is_well_formed() -> None:
    codes = [s.code for s in CORE]
    assert len(codes) == len(set(codes)) == 15
    assert {s.frequency for s in CORE} == {"daily", "monthly"}
    assert all(s.unit and s.description for s in CORE)


def test_parse_uit_handles_mixed_encoding_and_number_formats() -> None:
    html = (
        "<tr><td>2026</td><td>5,500</td><td>D.S. N° 301-2025-EF</td></tr>".encode()
        + "<tr><td>2003</td><td>3.100</td><td>D. S. N\xb0 191-2002-EF</td></tr>".encode("latin-1")
        + b"<tr><td>1996</td><td>2,200</td><td>D.S. N&deg; 012-96-EF</td></tr>"
        + b"<tr><td>1996</td><td>2.000</td><td>D.S. N&deg; 178-94-EF</td></tr>"
        + b"<tr><td>1992</td><td>1.040</td><td>D.S. N&deg; 307-91-EF</td></tr>"
    )
    assert parse_uit(html) == [
        (1996, 2200, "D.S. N° 012-96-EF"),  # primera fila del año
        (2003, 3100, "D.S. N° 191-2002-EF"),
        (2026, 5500, "D.S. N° 301-2025-EF"),
    ]  # 1992 se descarta (era URT)


def test_check_names_accepts_official_names() -> None:
    check_names(
        {
            "PD04638PD": "Tipo de cambio - TC Interbancario (S/ por US$) - Venta",
            "PD04722MM": "Tasas de interés del Banco Central de Reserva - Tasa de Referencia de la Política Monetaria",  # noqa: E501
            "PN07746EM": "Indicadores de las empresas bancarias - Cartera atrasada neta / Colocaciones netas (%) - Empresas Bancarias",  # noqa: E501
        }
    )


def test_check_names_detects_crossed_series() -> None:
    # Caso real: la API devuelve las series ordenadas por código; si se piden en
    # otro orden, la "tasa de referencia" recibe los datos del PBI.
    with pytest.raises(ValueError, match="PD04722MM"):
        check_names(
            {
                "PD04722MM": "Producto bruto interno y demanda interna (variación porcentual interanual) - PBI"  # noqa: E501
            }
        )
