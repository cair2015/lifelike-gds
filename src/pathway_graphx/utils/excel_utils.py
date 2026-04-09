#!/usr/bin/env python3
import numpy as np
import pandas as pd

from pathway_graphx.utils.pandas_utils import index2column


def write(fname, sheets: dict, indexes=None, format=True):
    """
    Write one or more DataFrames to an Excel workbook.
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
    Format an exported worksheet range as an Excel table.
    """
    options = {"columns": [{"header": col} for col in df.columns], "style": style}
    return sheet.add_table(
        startrow, startcol, startrow + df.shape[0], startcol + df.shape[1] - 1, options
    )
