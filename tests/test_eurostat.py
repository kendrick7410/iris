"""Smoke tests for Eurostat fetcher."""
import json
import tempfile
from pathlib import Path
from data.fetchers.eurostat import fetch_production, fetch_prices, fetch_turnover, fetch_gdp


def test_fetch_production():
    with tempfile.TemporaryDirectory() as td:
        cache = Path(td)
        out = fetch_production("2026-02", cache)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "eu27" in data
        assert "by_country" in data
        assert "by_sector" in data
        assert len(data["eu27"]) > 0
        print(f"  Production: {len(data['eu27'])} periods, latest={sorted(data['eu27'].keys())[-1]}")


def test_fetch_prices():
    with tempfile.TemporaryDirectory() as td:
        cache = Path(td)
        out = fetch_prices("2026-02", cache)
        assert out.exists()
        data = json.loads(out.read_text())
        assert len(data["eu27"]) > 0
        print(f"  Prices: {len(data['eu27'])} periods")


def test_fetch_turnover():
    with tempfile.TemporaryDirectory() as td:
        cache = Path(td)
        out = fetch_turnover("2026-02", cache)
        assert out.exists()
        data = json.loads(out.read_text())
        assert len(data["eu27"]) > 0
        print(f"  Turnover: {len(data['eu27'])} periods")


def test_fetch_gdp():
    with tempfile.TemporaryDirectory() as td:
        cache = Path(td)
        out = fetch_gdp("2026-02", cache)
        assert out.exists()
        data = json.loads(out.read_text())
        assert len(data["values"]) > 0
        print(f"  GDP: {data['values']}")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    print("Testing Eurostat fetcher...")
    test_fetch_production()
    test_fetch_prices()
    test_fetch_turnover()
    test_fetch_gdp()
    print("All Eurostat tests passed.")
