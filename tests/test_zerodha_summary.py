"""Tests for scripts/zerodha_summary.py, the read-only tradebook summary."""

from scripts import zerodha_summary as zs

HEADER = "symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,trade_id\n"


def write(tmp_path, name, rows):
    path = tmp_path / name
    path.write_text(HEADER + rows)
    return path


def test_mixed_segments_net_per_year(tmp_path):
    eq = write(tmp_path, "eq.csv", "INFY,I1,2026-01-05,NSE,EQ,EQ,buy,10,100,1\n"
                                   "INFY,I1,2026-02-05,NSE,EQ,EQ,sell,4,150,2\n")
    mf = write(tmp_path, "mf.csv", "FUND,I2,2026-03-01,BSE,MF,,buy,2.5,40,3\n")
    df, dropped = zs.load_tradebooks([eq, mf])
    table = zs.summarise(df, "year").set_index("segment")
    assert dropped == 0
    assert table.loc["Stocks", "buys"] == 1000
    assert table.loc["Stocks", "sells"] == 600
    assert table.loc["Stocks", "net"] == 400
    assert table.loc["Mutual funds", "net"] == 100


def test_overlapping_exports_are_deduplicated(tmp_path):
    row = "INFY,I1,2026-01-05,NSE,EQ,EQ,buy,10,100,1\n"
    a = write(tmp_path, "a.csv", row)
    b = write(tmp_path, "b.csv", row + "INFY,I1,2026-01-06,NSE,EQ,EQ,buy,1,100,2\n")
    df, dropped = zs.load_tradebooks([a, b])
    assert dropped == 1
    assert df["value"].sum() == 1100


def test_by_month_and_date_range(tmp_path, capsys):
    path = write(tmp_path, "mf.csv", "F,I,2026-07-01,BSE,MF,,buy,1,100,1\n"
                                     "F,I,2026-08-01,BSE,MF,,buy,1,200,2\n")
    assert zs.main([str(path), "--from", "2026-08-01", "--by", "month"]) == 0
    out = capsys.readouterr().out
    assert "2026-08" in out and "2026-07" not in out
