"""Scaffold a brand-new data folder: config.yaml + profiles/.

That's all the app needs to start (the history CSVs are created on first save):

    uv run python scripts/init_data_dir.py /path/to/FinanceData

Then rename/edit profiles/you.yaml (the filename stem becomes the profile key
in every CSV and the ?profile= URL), add one file per person, and point
DATA_DIR in .env at the folder. Existing files are never overwritten.
"""

import sys
from pathlib import Path

CONFIG = """\
# Shared asset-class vocabulary; targets and contributions may only use these.
categories: [us_market, indian_stocks, mfs, fixed_deposit, ppf_nps, bonds_gsec_aif, gold_metals]
"""

PROFILE = """\
name: You                   # display name (used only to pick the default profile)
birth_year: 1998
forward_increment_pct: 5    # assumed annual income growth for projected years
default_target:             # fallback allocation, must sum to 100
  mfs: 45
  gold_metals: 25
  indian_stocks: 14
  us_market: 10
  ppf_nps: 5
  bonds_gsec_aif: 1
"""


def write_once(path: Path, content: str) -> None:
    if path.exists():
        print(f"kept    {path} (already exists)")
        return
    path.write_text(content)
    print(f"created {path}")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: init_data_dir.py /path/to/FinanceData")
    root = Path(sys.argv[1]).expanduser()
    (root / "profiles").mkdir(parents=True, exist_ok=True)
    write_once(root / "config.yaml", CONFIG)
    write_once(root / "profiles" / "you.yaml", PROFILE)
    print(f"\nNext: rename profiles/you.yaml per person, then set DATA_DIR={root} in .env")


if __name__ == "__main__":
    main()
