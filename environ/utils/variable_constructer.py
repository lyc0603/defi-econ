import pandas as pd


def name_boom_interact_var(variable: str) -> str:
    """
    Name the boom interact variable.

    Args:
        variable (str): The name of the variable.

    Returns:
        str: The name of the boom interact variable.
    """
    return f"{variable}_boom"


def name_lag_variable(variable: str) -> str:
    """
    Name the lagged variable.

    Args:
        variable (str): The name of the variable.

    Returns:
        str: The name of the lagged variable.
    """
    return f"{variable}_lag"


def lag_variable(
    panel_data: pd.DataFrame,
    variable: str,
    time_variable: str,
    entity_variable: str = "",
) -> pd.DataFrame:
    """
    Lag the variable by lag 1.

    Args:
        data (pd.DataFrame): The dataset.
        variable (str): The name of the variable to lag.
        time_variable (str): The name of the time variable.
    """
    # Sort the dataset by the time variable
    panel_data = panel_data.sort_values(by=time_variable)

    # Lag the variable by lag 1
    # TODO: this assumes there is no gap in the time variable -- need to double check

    if entity_variable:
        panel_data[name_lag_variable(variable)] = panel_data.groupby(entity_variable)[
            variable
        ].shift(1)
    else:
        panel_data[name_lag_variable(variable)] = panel_data[variable].shift(1)

    return panel_data
