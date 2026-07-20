"""Tests for scripts/import_tradebook.py — the Zerodha tradebook importer.

Every test runs against a throwaway tmp_path data folder (config.yaml +
profiles/ + CSVs) and a synthetic tradebook CSV; the real DATA_DIR is never
touched.
"""

import pandas as pd
import pytest

from scripts import import_tradebook as imp
import storage

TRADEBOOK_HEADER = "symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price\n"


@pytest.fixture
def data_root(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "categories: [us_market, indian_stocks, mfs, fixed_deposit, ppf_nps, bonds_gsec_aif, gold_metals]\n"
    )
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "rv.yaml").write_text(
        "name: Rv\nbirth_year: 1998\nforward_increment_pct: 5\n"
        "default_target: {mfs: 100}\n"
    )
    return tmp_path


def write_tradebook(tmp_path, rows: str, name="tradebook.csv"):
    path = tmp_path / name
    path.write_text(TRADEBOOK_HEADER + rows)
    return path


def test_net_math(tmp_path):
    csv = write_tradebook(
        tmp_path,
        "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n"
        "INFY,INE1,2024-06-01,NSE,EQ,EQ,sell,4,1600\n",
    )
    df = imp.read_tradebook(csv)
    buys, sells, net, other = imp.year_totals(df, 2024)
    assert buys == 15000  # 10*1500
    assert sells == 6400  # 4*1600
    assert net == 8600
    assert other == {}


def test_year_filtering_reports_other_years(tmp_path):
    csv = write_tradebook(
        tmp_path,
        "INFY,INE1,2023-05-01,NSE,EQ,EQ,buy,5,1000\n"
        "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n"
        "INFY,INE1,2025-01-01,NSE,EQ,EQ,buy,2,1800\n",
    )
    df = imp.read_tradebook(csv)
    buys, sells, net, other = imp.year_totals(df, 2024)
    assert buys == 15000
    assert net == 15000
    assert other == {2023: 1, 2025: 1}


def test_auto_category_from_segment_eq(tmp_path):
    csv = write_tradebook(tmp_path, "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n")
    df = imp.read_tradebook(csv)
    in_year = df[pd.to_datetime(df["trade_date"]).dt.year == 2024]
    cat = imp.detect_category(in_year, None, ["indian_stocks", "mfs"])
    assert cat == "indian_stocks"


def test_auto_category_from_segment_mf(tmp_path):
    csv = write_tradebook(tmp_path, "PARAG,INF1,2024-03-01,NSE,MF,MF,buy,100,50\n")
    df = imp.read_tradebook(csv)
    in_year = df[pd.to_datetime(df["trade_date"]).dt.year == 2024]
    cat = imp.detect_category(in_year, None, ["indian_stocks", "mfs"])
    assert cat == "mfs"


def test_category_override_wins(tmp_path):
    csv = write_tradebook(tmp_path, "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n")
    df = imp.read_tradebook(csv)
    in_year = df[pd.to_datetime(df["trade_date"]).dt.year == 2024]
    cat = imp.detect_category(in_year, "gold_metals", ["indian_stocks", "gold_metals"])
    assert cat == "gold_metals"


def test_category_override_must_be_known(tmp_path):
    csv = write_tradebook(tmp_path, "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n")
    df = imp.read_tradebook(csv)
    in_year = df[pd.to_datetime(df["trade_date"]).dt.year == 2024]
    with pytest.raises(ValueError, match="not in config.yaml"):
        imp.detect_category(in_year, "not_a_category", ["indian_stocks"])


def test_mixed_segments_without_override_is_an_error(tmp_path):
    csv = write_tradebook(
        tmp_path,
        "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n"
        "PARAG,INF1,2024-03-01,NSE,MF,MF,buy,100,50\n",
    )
    df = imp.read_tradebook(csv)
    in_year = df[pd.to_datetime(df["trade_date"]).dt.year == 2024]
    with pytest.raises(ValueError, match="mixes categories"):
        imp.detect_category(in_year, None, ["indian_stocks", "mfs"])


def test_full_run_writes_via_storage(tmp_path, data_root):
    csv = write_tradebook(
        tmp_path,
        "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n"
        "INFY,INE1,2024-06-01,NSE,EQ,EQ,sell,4,1600\n",
    )
    code = imp.run(csv, "rv", 2024, None, replace=False, dry_run=False, root=data_root)
    assert code == 0
    df = pd.read_csv(data_root / "contributions.csv")
    row = df[(df["profile"] == "rv") & (df["year"] == 2024) & (df["category"] == "indian_stocks")]
    assert len(row) == 1
    assert row.iloc[0]["amount"] == 8600
    assert "Zerodha tradebook net" in row.iloc[0]["notes"]
    # Rides the audit log like any other save.
    assert (data_root / "changes.jsonl").exists()


def test_refuse_existing_without_replace(tmp_path, data_root):
    existing = pd.DataFrame([
        {"year": 2024, "profile": "rv", "category": "indian_stocks", "amount": 5000, "notes": "manual"},
    ])
    storage.save_contributions(data_root, existing)

    csv = write_tradebook(tmp_path, "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n")
    code = imp.run(csv, "rv", 2024, None, replace=False, dry_run=False, root=data_root)
    assert code == 1
    df = pd.read_csv(data_root / "contributions.csv")
    assert df.iloc[0]["amount"] == 5000  # untouched


def test_replace_swaps_the_one_row(tmp_path, data_root):
    existing = pd.DataFrame([
        {"year": 2024, "profile": "rv", "category": "indian_stocks", "amount": 5000, "notes": "manual"},
        {"year": 2024, "profile": "rv", "category": "mfs", "amount": 7000, "notes": "manual mfs"},
    ])
    storage.save_contributions(data_root, existing)

    csv = write_tradebook(tmp_path, "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n")
    code = imp.run(csv, "rv", 2024, None, replace=True, dry_run=False, root=data_root)
    assert code == 0
    df = pd.read_csv(data_root / "contributions.csv")
    stocks = df[(df["category"] == "indian_stocks")]
    assert len(stocks) == 1
    assert stocks.iloc[0]["amount"] == 15000
    mfs = df[df["category"] == "mfs"]
    assert mfs.iloc[0]["amount"] == 7000  # other category row untouched


def test_dry_run_writes_nothing(tmp_path, data_root):
    csv = write_tradebook(tmp_path, "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n")
    code = imp.run(csv, "rv", 2024, None, replace=False, dry_run=True, root=data_root)
    assert code == 0
    assert not (data_root / "contributions.csv").exists()
    assert not (data_root / "changes.jsonl").exists()


def test_negative_net_refused(tmp_path, data_root):
    csv = write_tradebook(
        tmp_path,
        "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,4,1000\n"
        "INFY,INE1,2024-06-01,NSE,EQ,EQ,sell,10,1000\n",
    )
    code = imp.run(csv, "rv", 2024, None, replace=False, dry_run=False, root=data_root)
    assert code == 1
    assert not (data_root / "contributions.csv").exists()


def test_unknown_profile_refused(tmp_path, data_root):
    csv = write_tradebook(tmp_path, "INFY,INE1,2024-03-01,NSE,EQ,EQ,buy,10,1500\n")
    code = imp.run(csv, "not_a_person", 2024, None, replace=False, dry_run=False, root=data_root)
    assert code == 1
