"""
Script to render the asset pricing table
"""

import pandas as pd

from environ.constants import (
    DEPENDENT_VARIABLES,
    PROCESSED_DATA_PATH,
    STABLE_DICT,
    TABLE_PATH,
)
from environ.process.asset_pricing.double_sorting import asset_pricing

# load the regression panel dataset
reg_panel = pd.read_pickle(
    PROCESSED_DATA_PATH / "panel_main.pickle.zip", compression="zip"
)

# table to store the results
df_tab = pd.DataFrame()

# stable non-stable info dict
stable_nonstable_info = {
    "stablecoin": reg_panel[reg_panel["Token"].isin(STABLE_DICT.keys())],
    "non-stablecoin": reg_panel[~reg_panel["Token"].isin(STABLE_DICT.keys())],
}

for panel_info, df_panel in stable_nonstable_info.items():
    for dominance in DEPENDENT_VARIABLES + ["ret"]:
        for frequency in [14, 30]:
            print(f"Processing {panel_info} {dominance} {frequency}")

            df_ap = asset_pricing(
                df_panel,
                dominance,
                3,
                frequency,
            ).T

            # save the results
            df_ap.to_latex(
                TABLE_PATH / f"asset_pricing_{panel_info}_{dominance}_{frequency}.tex",
                escape=False,
                header=False,
            )
