#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from xlsxwriter.worksheet import Worksheet

from lifelike_gds.utils.pandas_utils import index2column


def write(
    fname: str | Path,
    sheets: dict[str, pd.DataFrame],
    indexes: str | list[str] | None = None,
    format: bool = True,
) -> None:
    """
    Write one or more DataFrames to an Excel workbook.

    Args:
        fname: Output workbook path.
        sheets: Mapping from worksheet name to DataFrame.
        indexes: Optional index-column name or one name per sheet.
        format: When ``True``, format each worksheet as an Excel table.
    """
    with pd.ExcelWriter(fname, engine="xlsxwriter") as writer:
        for i_sheet, (sheet_name, df) in enumerate(sheets.items()):
            if indexes is not None:
                index = indexes if np.isscalar(indexes) else indexes[i_sheet]
                df = index2column(df, index)

            df.to_excel(writer, sheet_name=sheet_name, index=False)
            if format:
                format_as_table(df, writer.sheets[sheet_name])


def format_as_table(
    df: pd.DataFrame,
    sheet: Worksheet,
    startrow: int = 0,
    startcol: int = 0,
    style: str = "Table Style Light 8",
) -> Any:
    """
    Format an exported worksheet range as an Excel table.

    Args:
        df: DataFrame already written to the worksheet.
        sheet: Target XlsxWriter worksheet.
        startrow: Top row where the table begins.
        startcol: Left column where the table begins.
        style: Excel table style name.
    """
    options = {"columns": [{"header": col} for col in df.columns], "style": style}
    return sheet.add_table(
        startrow, startcol, startrow + df.shape[0], startcol + df.shape[1] - 1, options
    )
