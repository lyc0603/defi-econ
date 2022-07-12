# -*- coding: utf-8 -*-
"""
Download the historical data for AAVE from Dune Analytics
"""


from duneanalytics import DuneAnalytics
import pandas as pd
from pprint import pprint

def download_dune_data(dune_id): 
  # initialize client
  dune = DuneAnalytics('YOUR_DUNE_ACCOUNT', 'YOUR_DUNE_PASSWORD')

  # try to login
  dune.login()

  # fetch token
  dune.fetch_auth_token()

  # fetch query result id using query id
  # query id for any query can be found from the url of the query:
  # for example: 
  # https://dune.com/queries/4494/8769 => 4494
  # https://dune.com/queries/3705/7192 => 3705
  # https://dune.com/queries/3751/7276 => 3751

  result_id = dune.query_result_id(query_id=dune_id)

  # fetch query result
  data = dune.query_result(result_id)

  # filter the raw result
  result_dict = data['data']['get_result_by_result_id']

  return result_dict

if __name__ == "__main__": 
  # data source: https://dune.com/queries/589140/1100732
  result_dict = download_dune_data(589140)

  # Initialize the dataframe for storing the result from dictionary
  df_result = pd.DataFrame()

  # read the result dict row by row
  for index in range(len(result_dict)):
    new_entity = pd.DataFrame(result_dict[index]['data'], index=[index])
    df_result = pd.concat([df_result, new_entity], ignore_index=True, axis=0)

  # reorder the column
  df_result = df_result[['day', 'symbol', 'deposit', 'borrow']]

  df_result.to_csv("data_aave/aave_top_token_historical_data.csv")
