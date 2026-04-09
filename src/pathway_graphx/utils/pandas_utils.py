#!/usr/bin/env python3
import pandas as pd


def index2column(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """
    Put the current index into the first column and reset to a default index.
    """
    return df.reset_index().rename(columns=dict(index=name))
