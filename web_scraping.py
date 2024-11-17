# -*- coding: utf-8 -*-
"""最終スクレイピング.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1u8Le5BPv7gp8BXTbvaGErBhOUjii4K2s
"""

import os
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import re
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

EMAIL = ""
PASSWORD = ""

# 1. セッションを開始する関数
def start_session():
    """Start a session and return it."""
    return requests.Session()

# 2. ログインする関数
def login(session):
    """Log in to the website."""
    login_url = "https://soubakensaku.com/search/data.php?c=login"
    login_payload = {
        'login_id': EMAIL,
        'login_pass': PASSWORD,
        'page': 'login'
    }
    response = session.post(login_url, data=login_payload)

    # ログイン成功の確認
    if response.status_code != 200 or "ログインに失敗しました" in response.text:
        logging.error("Login failed: Invalid email or password.")
        raise Exception("Login failed")
    logging.info("Logged in successfully.")

# 3. 最終ページを取得する関数
def get_last_page_number(session, large_class):
    """ページナビゲーションから最終ページの番号を取得する。"""
    page_url = f"https://soubakensaku.com/search/data.php?c=search_thumb_m&free2=&name=&model_no=&large_class={large_class}&holding=&contract_price=between&contract_price_A=0&contract_price_B=999999999"
    response = session.get(page_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # 最終ページ番号を取得
    page_navi = soup.find('div', class_='page_navi')
    if page_navi:
        last_page_link = page_navi.find_all('a')[-1]
        if last_page_link and 'page=' in last_page_link['href']:
            last_page_number = int(re.search(r'page=(\d+)', last_page_link['href']).group(1))
            logging.info(f"最終ページ番号を取得: {last_page_number}")
            return last_page_number
    return None

# 4. アイテム情報を抽出する関数
def extract_item_info(soup):
    """アイテム情報を抽出する。"""
    item_info = {}
    table = soup.find('table')
    if not table:
        return item_info  # テーブルが見つからない場合は空の辞書を返す
    for row in table.find_all('tr'):
        ths = row.find_all('th')
        tds = row.find_all('td')
        if len(ths) == len(tds):
            for th, td in zip(ths, tds):
                key = th.get_text(strip=True)
                value = td.get_text(strip=True)
                item_info[key] = value
    return item_info

# 5. データを保存する関数
def save_to_csv(data_list, filename):
    """指定されたファイル名にデータをCSVとして保存（追記モード）。"""
    df = pd.DataFrame(data_list)
    # If the file exists, append without header
    if os.path.exists(filename):
        df.to_csv(filename, mode='a', header=False, index=False)
    else:
        df.to_csv(filename, index=False)
    logging.info(f'{len(data_list)}件のデータを{filename}に保存しました。')

# 6. 既存のCSVから取得済みのアイテム数を確認
def get_existing_data_count(filename):
    """既存のCSVファイルからすでに保存されたアイテムの数を取得する。"""
    if os.path.exists(filename):
        existing_df = pd.read_csv(filename)
        return len(existing_df)
    return 0

# 7. メインの処理
def main():
    parser = argparse.ArgumentParser(description="Scrape item information and save to CSV.")
    parser.add_argument("--large_class", type=str, required=True, choices=["時計", "宝石・貴金属", "BRジュエリー", "小物", "衣料品", "その他"], help="大分類の選択")
    parser.add_argument("--output", type=str, default="output.csv", help="保存するCSVファイル名")
    parser.add_argument("--save_count", type=int, default=100, help="指定されたアイテム数ごとに保存するカウント数")
    parser.add_argument("--start_page", type=int, default=1, help="抽出を開始するページ番号")
    args = parser.parse_args()

    # セッションを開始し、ログイン
    session = start_session()
    login(session)

    # 最終ページを取得
    end_page = get_last_page_number(session, args.large_class)
    if end_page is None:
        logging.error("最終ページ番号を取得できませんでした。")
        return

    # CSVに保存済みのデータ数を確認し、続きから取得する
    total_saved_items = get_existing_data_count(args.output)
    data_list = []  # 保存するデータのリストを初期化

    current_page = args.start_page
    while current_page <= end_page:
        try:
            logging.info(f'{current_page} ページを処理中...')

            # 現在のページのURLを構築
            data_url = f"https://soubakensaku.com/search/data.php?c=search_thumb_m&free2=&name=&model_no=&large_class={args.large_class}&holding=&contract_price=between&contract_price_A=0&contract_price_B=999999999&order_key=update_unix&order=ASC&page={current_page}"

            response = session.get(data_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # 各ページからアイテムIDを抽出
            items = re.findall(r'item=(\d+)', response.text)
            unique_items = list(set(items))

            # アイテムごとに詳細ページを訪問してデータを取得
            for idx, item in enumerate(unique_items):
                try:
                    logging.info(f'ページ {current_page} のアイテム {idx+1}/{len(unique_items)} を処理中...')

                    # アイテムの詳細URLを構築
                    url = f'https://soubakensaku.com/search/data.php?c=info_m&item={item}'
                    response = session.get(url)
                    soup = BeautifulSoup(response.content, 'html.parser')

                    # アイテム情報を抽出
                    item_info = extract_item_info(soup)

                    # データリストに追加
                    data_list.append(item_info)

                    # 指定されたカウント数に達したらCSVに保存
                    if len(data_list) >= args.save_count:
                        save_to_csv(data_list, args.output)
                        total_saved_items += len(data_list)
                        data_list = []  # 保存したのでリストをクリア

                    # サーバーへの負荷を避けるために待機
                    time.sleep(1)
                except Exception as e:
                    logging.error(f'アイテム {item} の処理中にエラーが発生しました: {e}')

            current_page += 1
        except Exception as e:
            logging.error(f'ページ {current_page} の処理中にエラーが発生しました: {e}')
            break

    # 残りのデータを保存
    if data_list:
        save_to_csv(data_list, args.output)

    logging.info(f'データの抽出と保存が完了しました。抽出したページは{args.start_page}ページから{end_page}ページまでです。')

# メイン処理の実行
if __name__ == "__main__":
    main()