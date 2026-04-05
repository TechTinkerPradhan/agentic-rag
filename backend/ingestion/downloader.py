"""Download SEC EDGAR filings and create the revenue CSV fixture."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
from sec_edgar_downloader import Downloader

from backend.config import get_settings
from backend.observability.weave_client import weave_op

logger = logging.getLogger(__name__)


@weave_op()
def download_sec_filings(
    ticker: str | None = None,
    limit_10k: int = 1,
    limit_10q: int = 4,
    limit_8k: int = 1,
    limit_proxy: int = 1,
) -> list[Path]:
    """Download SEC filings for *ticker* and return the list of found files."""
    cfg = get_settings()
    ticker = ticker or cfg.sec_ticker

    # sec_edgar_downloader always creates sec-edgar-filings/ inside download_folder;
    # pass data_dir so it lands at data_dir/sec-edgar-filings/<ticker>/
    dl = Downloader(cfg.company_name, cfg.company_email, str(cfg.data_dir))
    dl.get("10-K", ticker, limit=limit_10k)
    dl.get("10-Q", ticker, limit=limit_10q)
    dl.get("8-K", ticker, limit=limit_8k)
    dl.get("DEF 14A", ticker, limit=limit_proxy)

    return find_filing_files(ticker)


def find_filing_files(ticker: str | None = None) -> list[Path]:
    """Return paths to all full-submission.txt files already on disk.

    sec_edgar_downloader always creates sec-edgar-filings/<ticker>/ inside
    the download_folder we pass it, so the actual path is:
        cfg.sec_dir / "sec-edgar-filings" / ticker
    """
    cfg = get_settings()
    ticker = ticker or cfg.sec_ticker
    data_path = cfg.sec_dir / "sec-edgar-filings" / ticker

    if not data_path.exists():
        return []

    files: list[Path] = []
    for root, _, filenames in os.walk(data_path):
        for fname in filenames:
            if fname == "full-submission.txt":
                files.append(Path(root) / fname)

    logger.info("Found %d filing files for %s", len(files), ticker)
    return files


@weave_op()
def create_revenue_csv() -> Path:
    """Create (or overwrite) the revenue_summary.csv fixture and return its path."""
    cfg = get_settings()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)

    revenue_data = {
        "year": [2023, 2023, 2023, 2023, 2022, 2022, 2022, 2022],
        "quarter": ["Q4", "Q3", "Q2", "Q1", "Q4", "Q3", "Q2", "Q1"],
        "revenue_usd_billions": [61.9, 56.5, 52.9, 52.7, 51.9, 50.1, 49.4, 51.7],
        "net_income_usd_billions": [21.9, 22.3, 17.4, 16.4, 17.6, 16.7, 16.7, 18.8],
    }

    df = pd.DataFrame(revenue_data)
    df.to_csv(cfg.revenue_csv_path, index=False)
    logger.info("Revenue CSV written to %s", cfg.revenue_csv_path)
    return cfg.revenue_csv_path
