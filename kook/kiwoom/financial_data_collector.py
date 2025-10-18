#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pykrx로 시가총액, 종가, 상장주식수 데이터 수집 및 저장
"""
import pandas as pd
from pykrx import stock
import os

def collect_market_cap_history(
    date_list, market="KOSPI", save_path="data/market_cap_history.csv"
):
    result = []
    for date in date_list:
        print(f"{date} 데이터 수집 중...")
        df = stock.get_market_cap_by_ticker(date, market=market)
        df = df.reset_index()
        df['date'] = date
        result.append(df)
    final_df = pd.concat(result, ignore_index=True)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    final_df.to_csv(save_path, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {save_path}")

if __name__ == "__main__":
    # 예시: 2023년 월말 데이터 수집
    date_list = [
        "20230131", "20230228", "20230331", "20230428", "20230531", "20230630",
        "20230731", "20230831", "20230929", "20231031", "20231130", "20231229"
    ]
    collect_market_cap_history(date_list, market="KOSPI", save_path="data/market_cap_history_kospi_2023.csv")
    collect_market_cap_history(date_list, market="KOSDAQ", save_path="data/market_cap_history_kosdaq_2023.csv") 