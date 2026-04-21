"""Smoke tests for Comext stub."""
import json
import tempfile
from pathlib import Path
from data.fetchers.comext import read_parquet


def test_comext_unavailable():
    """Without COMEXT_DATA_PATH, should produce trade_unavailable.json."""
    import os
    os.environ.pop("COMEXT_DATA_PATH", None)

    with tempfile.TemporaryDirectory() as td:
        cache = Path(td)
        out = read_parquet("2026-02", cache)
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["status"] == "unavailable"
        print(f"  Comext stub: {data['reason']}")


if __name__ == "__main__":
    print("Testing Comext stub...")
    test_comext_unavailable()
    print("All Comext tests passed.")
