from datetime import date

import pytest

from pipelines.extractors.bcrp import parse_payload, parse_period, parse_value
from pipelines.extractors.uit import parse_uit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("02.Ene.25", date(2025, 1, 2)),
        ("01.Set.25", date(2025, 9, 1)),  # septiembre diario = "Set"
        ("15.Dic.99", date(1999, 12, 15)),
        ("Sep.2025", date(2025, 9, 1)),  # septiembre mensual = "Sep"
        ("Ene.2000", date(2000, 1, 1)),
    ],
)
def test_parse_period(raw: str, expected: date) -> None:
    assert parse_period(raw) == expected


def test_parse_period_rejects_unknown_format() -> None:
    with pytest.raises(ValueError):
        parse_period("T1.2025")


def test_parse_value() -> None:
    assert parse_value("3.5415") == pytest.approx(3.5415)
    assert parse_value("n.d.") is None
    assert parse_value(" ") is None


def test_parse_payload_skips_missing_values() -> None:
    payload = {
        "periods": [
            {"name": "05.Ago.25", "values": ["3.55"]},
            {"name": "06.Ago.25", "values": ["n.d."]},
            {"name": "07.Ago.25", "values": ["3.54"]},
        ]
    }
    assert parse_payload(payload) == [(date(2025, 8, 5), 3.55), (date(2025, 8, 7), 3.54)]


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
