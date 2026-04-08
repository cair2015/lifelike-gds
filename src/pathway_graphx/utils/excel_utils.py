#!/usr/bin/env python3
import numpy as np
import pandas as pd

from pathway_graphx.utils.pandas_utils import index2column


def write(fname, sheets: dict, indexes=None, format=True):
    """
    Write excel table.
    :param fname: write to this filename or stream
    :param sheets: dict mapping from sheet name to pandas DataFrame
    :param indexes: optionally keep indexes by converting them to a normal column with these string names in a list
    :param format: format as table.
    """
    with pd.ExcelWriter(fname, engine="xlsxwriter") as writer:
        for i_sheet, (sheet_name, df) in enumerate(sheets.items()):
            if indexes is not None:
                index = indexes if np.isscalar(indexes) else indexes[i_sheet]
                df = index2column(df, index)

            df.to_excel(writer, sheet_name=sheet_name, index=False)
            if format:
                format_as_table(df, writer.sheets[sheet_name])


def format_as_table(df, sheet, startrow=0, startcol=0, style="Table Style Light 8"):
    """
    Format as table so columns can easily be filtered, sorted etc.
    """
    options = {"columns": [{"header": col} for col in df.columns], "style": style}
    return sheet.add_table(
        startrow, startcol, startrow + df.shape[0], startcol + df.shape[1] - 1, options
    )
