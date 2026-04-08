#!/usr/bin/env python3
import pandas as pd


def index2column(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """
    Put index as a column with the given name. Puts it as first column.
    Drops the index resetting it to a default integer index.
    """
    return df.reset_index().rename(columns=dict(index=name))
