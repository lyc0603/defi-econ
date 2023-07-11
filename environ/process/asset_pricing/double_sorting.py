"""
Functions to help with asset pricing
"""

import datetime
import warnings

import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
from tqdm import tqdm

from environ.constants import DEPENDENT_VARIABLES, PROCESSED_DATA_PATH, STABLE_DICT
from environ.process.market.risk_free_rate import df_rf
from environ.utils.variable_constructer import lag_variable_columns, name_lag_variable

warnings.filterwarnings("ignore")

FONT_SIZE = 25


def _apr_return(
    df_panel: pd.DataFrame,
    freq: int,
) -> pd.DataFrame:
    """
    Function to calculate the APY return
    """

    # convert annalized supply rates to daily supply rates
    df_panel["supply_rates"] = df_panel["supply_rates"] / 365

    # sort the dataframe by Token and Date
    df_panel.sort_values(by=["Token", "Date"], ascending=True, inplace=True)

    # iterate through the Token
    for token in tqdm(df_panel["Token"].unique()):
        # isolate the dataframe by Token
        df_token = df_panel[df_panel["Token"] == token]

        # get the list of date when the frequency is True
        date_list = df_token[df_token["freq"]]["Date"].tolist()

        # iterate through the date list
        for date in date_list:
            # isolate the dataframe between the date and the date - freq + 1
            df_date = df_token[
                (df_token["Date"] <= date)
                & (df_token["Date"] > date - datetime.timedelta(days=freq))
            ].copy()

            # compound the apy
            cum_apy = (df_date["supply_rates"] + 1).prod() - 1

            df_panel.loc[
                (df_panel["Token"] == token) & (df_panel["Date"] == date), "cum_apy"
            ] = cum_apy

            df_panel.loc[
                (df_panel["Token"] == token) & (df_panel["Date"] == date),
                "dollar_exchange_rate_mom",
            ] = df_panel.loc[
                (df_panel["Token"] == token)
                & (df_panel["Date"] == (date - datetime.timedelta(days=freq))),
                "dollar_exchange_rate",
            ]

    # calculate the DPY return
    df_panel["apr_ret"] = (1 + df_panel["cum_apy"]) * (df_panel["dollar_ret"] + 1) - 1

    # calculate the aggregate return
    df_panel["ret"] = df_panel["apr_ret"] + df_panel["dollar_ret"]

    return df_panel


def _freq_conversion(
    df_panel: pd.DataFrame,
    freq: int,
    date_col: str = "Date",
) -> pd.DataFrame:
    """
    Function to convert the frequency of a series from daily to a given frequency
    """

    # convert the date to datetime
    df_panel["timestamp"] = df_panel[date_col].apply(lambda x: int(x.timestamp()))

    # create a freq column
    df_panel["freq"] = (
        (df_panel["timestamp"] - df_panel["timestamp"].min()) % (freq * 24 * 60 * 60)
    ) == 0

    # keep the row with freq == True
    df_panel = df_panel[df_panel["freq"]]

    # check if the frequency is year or month
    df_panel.sort_values(by=["Token", "Date"], ascending=True, inplace=True)

    # calculate the return under the new frequency
    df_panel["dollar_ret"] = df_panel.groupby("Token")[
        "dollar_exchange_rate"
    ].pct_change()
    df_panel["mret"] = df_panel.groupby("Token")["S&P"].pct_change()

    return df_panel


def _ret_winsorizing(
    df_panel: pd.DataFrame,
    threshold: float = 0.01,
    ret_col: str = "dollar_ret",
) -> pd.DataFrame:
    """
    Function to winsorize the DataFrame
    """

    # winsorize the return
    df_panel.loc[
        df_panel[ret_col] <= df_panel[ret_col].quantile(threshold), ret_col + "w"
    ] = df_panel[ret_col].quantile(threshold)
    df_panel.loc[
        df_panel[ret_col] >= df_panel[ret_col].quantile(1 - threshold), ret_col + "w"
    ] = df_panel[ret_col].quantile(1 - threshold)

    return df_panel


def _asset_pricing_preprocess(
    df_panel: pd.DataFrame,
    dominance_var: str,
    freq: int,
) -> pd.DataFrame:
    """
    Function to preprocess the dataframe
    """

    # convert the frequency
    df_panel = _freq_conversion(df_panel, freq=freq)

    # winsorize the return
    df_panel = _ret_winsorizing(df_panel)

    # apr return
    df_panel = _apr_return(df_panel, freq=freq)

    # lag 1 unit for the dominance var and yield var to avoid information leakage
    df_panel = lag_variable_columns(
        data=df_panel,
        variable=[dominance_var],
        time_variable="Date",
        entity_variable="Token",
    )

    return df_panel


def _sort_zero_value_port(
    df_panel_period: pd.DataFrame,
    risk_factor: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Function to isolate zero-value dominance portfolio
    """

    # isolate the portfolio with zero dominance
    df_zero_dom = df_panel_period[
        df_panel_period[name_lag_variable(risk_factor)] == 0
    ].copy()

    df_zero_dom["portfolio"] = "P1"

    # remove the tokens with zero dominance
    df_panel_period = df_panel_period[
        df_panel_period[name_lag_variable(risk_factor)] != 0
    ].copy()

    return df_panel_period, df_zero_dom


def _sorting(
    df_panel_period: pd.DataFrame,
    risk_factor: str,
    n_port: int = 3,
    zero_value_portfolio: bool = True,
) -> pd.DataFrame:
    """
    Function to implement the asset pricing for one period
    """

    # a list to store the top portfolio and bottom portfolio
    df_portfolio = []

    if zero_value_portfolio:
        # isolate the zero-value portfolio
        df_panel_period, df_zero_dom = _sort_zero_value_port(
            df_panel_period=df_panel_period, risk_factor=risk_factor
        )
        df_portfolio.append(df_zero_dom)

    # sort the dataframe based on the risk factor
    df_panel_period = df_panel_period.sort_values(
        by=name_lag_variable(risk_factor), ascending=True
    )

    # rows per partition
    n_threasold = len(df_panel_period) // n_port

    for port in range(n_port - 2) if zero_value_portfolio else range(n_port - 1):
        # isolate the portfolio
        df_portfolio_period = df_panel_period.iloc[
            port * n_threasold : (port + 1) * n_threasold
        ].copy()

        # add the portfolio column
        df_portfolio_period["portfolio"] = (
            f"P{port + 2}" if zero_value_portfolio else f"P{port + 1}"
        )

        # append the dataframe
        df_portfolio.append(df_portfolio_period)

    # isolate the portfolio
    df_portfolio_period = df_panel_period.iloc[(n_port - 1) * n_threasold :].copy()

    # add the portfolio column
    df_portfolio_period["portfolio"] = f"P{n_port}"

    # append the dataframe
    df_portfolio.append(df_portfolio_period)

    return pd.concat(df_portfolio)


def _mcap_weight(df_portfolio: pd.DataFrame, ret_dict: dict) -> dict:
    """
    Function to calculate the market cap weight
    """

    # check how many portfolio
    n_port = len(df_portfolio["portfolio"].unique())

    for portfolio in [f"P{port}" for port in range(1, n_port + 1)]:
        # calculate the market cap weight
        df_portfolio["weight"] = df_portfolio["mcap"] / df_portfolio["mcap"].sum()
        ret_dict[portfolio].append((df_portfolio["weight"] * df_portfolio["ret"]).sum())

    return ret_dict


def _eval_port(
    df_ret: pd.DataFrame,
    freq: int,
    n_port: int,
) -> pd.DataFrame:
    """
    Function to evaluate the portfolio
    """

    # prepare the dataframe
    df_ret.sort_values(by="freq", ascending=True, inplace=True)
    df_ret["freq"] = pd.to_datetime(df_ret["freq"])

    # include the risk free rate
    df_rf_ap = df_rf.copy()
    df_rf_ap.rename(columns={"Date": "freq"}, inplace=True)
    df_rf_ap["RF"] = (1 + df_rf_ap["RF"]) ** freq - 1
    df_ret = df_ret.merge(df_rf_ap, on="freq", how="left")

    # calculate the excess return
    for portfolio in [f"P{port}" for port in range(1, n_port + 1)]:
        df_ret[portfolio] = df_ret[portfolio] - df_ret["RF"]

    # calculate the bottom minus top
    df_ret[f"P{n_port} - P1"] = df_ret[f"P{n_port}"] - df_ret["P1"]

    portfolio_col = [f"P{port}" for port in range(1, n_port + 1)] + [f"P{n_port} - P1"]

    # a new dataframe to store the averag return for each portfolio
    df_ret_avg = pd.DataFrame(
        {
            # portfolio name
            "Portfolios": portfolio_col,
            # average return
            "Mean": [round(num, 3) for num in df_ret[portfolio_col].mean().to_list()],
            # t-stat of the average return
            "t-stat of mean": df_ret[portfolio_col]
            .apply(lambda x: stats.ttest_1samp(x, 0)[0])
            .to_list(),
            # p-value of the average return
            "p-value of mean": df_ret[portfolio_col]
            .apply(lambda x: stats.ttest_1samp(x, 0)[1])
            .to_list(),
            # standard deviation of the return
            "Stdev": df_ret[portfolio_col].std().to_list(),
            # sharpe ratio
            "Sharpe": (
                df_ret[portfolio_col].mean() / df_ret[portfolio_col].std()
            ).to_list(),
            # alpha of the portfolio
            "Alpha": df_ret[portfolio_col]
            .apply(lambda x: sm.OLS(x, df_ret["mret"] - df_ret["RF"]).fit().params[0])
            .to_list(),
            # t-stat of the alpha
            "t-stat of alpha": df_ret[portfolio_col]
            .apply(lambda x: sm.OLS(x, df_ret["mret"] - df_ret["RF"]).fit().tvalues[0])
            .to_list(),
        }
    )

    return df_ret_avg


def asset_pricing(
    reg_panel: pd.DataFrame,
    dom_var: str = "volume_ultimate_share",
    n_port: int = 3,
    freq: int = 14,
    zero_value_portfolio: bool = True,
) -> pd.DataFrame:
    """
    Aggregate function to create portfolios
    """

    # preprocess the dataframe
    df_panel = _asset_pricing_preprocess(reg_panel, dom_var, freq)

    # prepare the dataframe to store the portfolio
    df_panel = df_panel.sort_values(by=["Date"], ascending=True)
    date_list = list(df_panel["Date"].unique())
    date_list.remove(df_panel["Date"].min())
    # dict to store the freq and portfolio return
    ret_dict = {f"P{port}": [] for port in range(1, n_port + 1)}
    ret_dict["freq"] = []
    ret_dict["mret"] = []

    # loop through the date
    for period in date_list:
        # asset pricing
        df_panel_period = df_panel[df_panel["Date"] == period].copy()
        df_portfolio = _sorting(
            df_panel_period=df_panel_period,
            risk_factor=dom_var,
            n_port=n_port,
            zero_value_portfolio=zero_value_portfolio,
        )

        # mcap weight
        ret_dict["freq"].append(period)
        ret_dict["mret"].append(df_panel_period["mret"].mean())
        ret_dict = _mcap_weight(df_portfolio, ret_dict)

    # evaluate the performance of the portfolio
    return _eval_port(pd.DataFrame(ret_dict), freq, n_port)


if __name__ == "__main__":
    # load the regression panel dataset
    reg_panel = pd.read_pickle(
        PROCESSED_DATA_PATH / "panel_main.pickle.zip", compression="zip"
    )

    # stable non-stable info dict
    stable_nonstable_info = {
        "stablecoin": reg_panel[reg_panel["Token"].isin(STABLE_DICT.keys())],
        "non-stablecoin": reg_panel[~reg_panel["Token"].isin(STABLE_DICT.keys())],
    }

    # iterate through the dominance
    for panel_info, df_panel in stable_nonstable_info.items():
        for dominance in DEPENDENT_VARIABLES + ["ret"]:
            for frequency in [14, 30]:
                print(f"Processing {panel_info} {dominance} {frequency}")

                print(
                    asset_pricing(
                        df_panel,
                        dominance,
                        3,
                        frequency,
                    )
                )
