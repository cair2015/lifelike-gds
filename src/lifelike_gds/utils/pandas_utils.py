#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd


def index2column(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """
    Move the current index into a named column and reset to a default index.

    Args:
        df: Source DataFrame.
        name: Column name to use for the exported index values.

    Returns:
        A new DataFrame with the previous index stored as the first column.
    """
    return df.reset_index().rename(columns=dict(index=name))
