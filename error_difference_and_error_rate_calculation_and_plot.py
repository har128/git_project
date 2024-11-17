# -*- coding: utf-8 -*-
"""8.誤差の差分と誤差率の計算とプロット.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1GhtVIvZtTVR9j0kX-u9beCz0X9OwLAJY
"""

# 必要なライブラリのインストール
!pip install lightgbm
!pip install optuna
!pip install --upgrade lightgbm
!pip install matplotlib
!pip install japanize_matplotlib

# フォントのインストール
!apt-get -y install fonts-noto-cjk

# 日本語フォントをmatplotlibで使用可能にする
import matplotlib.font_manager as fm

# フォントキャッシュを手動で指定して再構築（キャッシュが古い場合のみ必要）
fm._load_fontmanager(try_read_cache=False)

# Pandasライブラリのインストール（必要であれば）
!pip install pandas

# Scikit-learnのインストール
!pip install scikit-learn

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import japanize_matplotlib
import seaborn as sns
import unicodedata
import re
import gc
import optuna
from scipy import stats
import statsmodels.api as sm
from datetime import timedelta

from sklearn.model_selection import train_test_split, KFold
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_percentage_error, mean_absolute_error

import lightgbm as lgb
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder, StandardScaler

import matplotlib.font_manager as fm

# CSVファイルを読み込み
file_paths = [
    '/content/sample_data/market_products_info_2024-09-09_limit100_category8_from2020-01-01_to2020-12-31_page_from1.csv',
    '/content/sample_data/market_products_info_2024-09-10_limit100_category8_from2021-01-01_to2024-12-31_page_from122.csv',
    '/content/sample_data/market_products_info_2024-09-10_limit100_category8_from2021-01-01_to2024-12-31_page_from1_to73.csv',
    '/content/sample_data/market_products_info_2024-09-10_limit100_category8_from2021-01-01_to2024-12-31_page_from74_to121.csv'
]

# データの読み込みと結合
data_frames = [pd.read_csv(file_path) for file_path in file_paths]
data = pd.concat(data_frames, ignore_index=True)

# カテゴリの結合処理
data['Medium category'] = data['Medium category'].replace({
    'フラットシューズ': 'Flat shoes',
    'sandals': 'Sandals'
})
valid_categories = ['Sneakers', 'Pumps', 'Sandals', 'Boots', 'Loafer', 'Leather shoes', 'Slip-on', 'Flat shoes']
data['Medium category'] = data['Medium category'].apply(lambda x: x if x in valid_categories else 'Other')

data['Brand'] = data['Brand'].replace({'ドルチェ&ガッバーナ': 'Dolce & Gabbana'})
data['Category'] = data['Category'].replace({'ソックスブーツ': 'SOCK BOOTS', 'プラットフォームシューズ': 'Platform shoes'})
data['Materials'] = data['Materials'].replace({
    'レザー×ファブリック': 'Leather x fabric',
    'メッシュ×レザー': 'Mesh x leather',
    'レザー×メッシュ': 'Mesh x leather',
    'スエード×ナイロン': 'Suede x nylon'
})
data['Color'] = data['Color'].replace({
    'ブラック': 'Black', 'ブルー×ホワイト': 'Blue x white', 'レッド×ホワイト': 'Blue x white',
    'Black x red': 'Red x Black', 'ホワイト×ピンク': 'White x pink', 'ブラック×ピンク': 'Black x pink',
    'gold×black': 'Black×Gold', 'ホワイト×ブラウン': 'White x brown', 'ブラック×イエロー': 'Black x yellow',
    'グリーン×ブラック': 'Black x green', 'Black x green': 'Black x green', 'レッド×ブラウン': 'Red x brown',
    'Green x yellow': 'Green x yellow', 'イエロー×グリーン': 'Green x yellow'
})
data['Lift'] = data['Lift'].replace({
    'stain': 'スレ有', 'Is there a thread': 'スレ有', 'There is a thread': 'スレ有',
    'rubbed': 'スレ有', 'Has thread': 'スレ有', 'Rubbous': 'スレ有',
    'No obvious wears': '-'
})
data['Sole'] = data['Sole'].replace({
    'Scrape': 'スレあり', 'すれ有': 'スレあり', 'Rubbed': 'スレあり',
    'ソール補修あり': 'ソール補修あり', '-': '-', 'No obvious wears': 'No obvious wears'
})
data['Dirt'] = data['Dirt'].replace({
    'There is a stale': 'ヨゴレあり', 'soiled': 'ヨゴレあり', 'Stained': 'ヨゴレあり',
    '-': '-'
})

# 必要な列を選択
selected_columns = ['successful_bid_price', 'Medium category', 'Category', 'Brand', 'Materials', 'Color',
                    'Gender', 'Width (cm)', 'Height (cm)', 'Lift', 'Sole', 'Dirt', 'Heel height (cm)']
data_selected = data[selected_columns]

# 欠損しているターゲット値（successful_bid_price）の行を削除
data_selected = data_selected.dropna(subset=['successful_bid_price'])

# 欠損値を埋める
data_selected.fillna(-999, inplace=True)

# 数値型の列を正しい型に変換
numeric_columns = ['Width (cm)', 'Height (cm)', 'Heel height (cm)']
for col in numeric_columns:
    data_selected[col] = pd.to_numeric(data_selected[col], errors='coerce')
data_selected.fillna(-999, inplace=True)

# 'Brand'の元のデータを保持
data_selected['Brand_original'] = data_selected['Brand']

# ラベルエンコーディング対象のカテゴリ列
categorical_columns = ['Medium category', 'Category', 'Brand', 'Materials', 'Color', 'Gender',
                       'Lift', 'Sole', 'Dirt']

# ラベルエンコーディング
label_encoders = {}
for col in categorical_columns:
    if data_selected[col].dtype == 'object':
        le = LabelEncoder()
        data_selected[col] = le.fit_transform(data_selected[col].astype(str))
        label_encoders[col] = le

# 過去の平均値を'Brand', 'Category', 'Medium category'で計算
data_selected['brand_avg_price'] = data_selected.groupby('Brand')['successful_bid_price'].expanding().mean().reset_index(level=0, drop=True)
data_selected['category_avg_price'] = data_selected.groupby('Category')['successful_bid_price'].expanding().mean().reset_index(level=0, drop=True)
data_selected['medium_category_avg_price'] = data_selected.groupby('Medium category')['successful_bid_price'].expanding().mean().reset_index(level=0, drop=True)

# 欠損値処理
data_selected['brand_avg_price'].fillna(-999, inplace=True)
data_selected['category_avg_price'].fillna(-999, inplace=True)
data_selected['medium_category_avg_price'].fillna(-999, inplace=True)

# ラグ特徴量の作成
data_selected['price_lag_1'] = data_selected['successful_bid_price'].shift(1)
data_selected['price_lag_2'] = data_selected['successful_bid_price'].shift(2)
data_selected['price_lag_3'] = data_selected['successful_bid_price'].shift(3)

# 移動平均特徴量の作成
data_selected['price_rolling_mean_7'] = data_selected['successful_bid_price'].rolling(window=7).mean()
data_selected['price_rolling_mean_30'] = data_selected['successful_bid_price'].rolling(window=30).mean()

# NaNがある行は削除
data_selected = data_selected.dropna()

# 対数変換（異常値に対する対策）
data_selected = data_selected[data_selected['successful_bid_price'] > 0]
data_selected['log_successful_bid_price'] = np.log1p(data_selected['successful_bid_price'])

# 特徴量の定義
X = data_selected.drop(['successful_bid_price', 'log_successful_bid_price'], axis=1)
y = data_selected['log_successful_bid_price']

# KFoldでクロスバリデーションを行い、モデルを訓練
kf = KFold(n_splits=5, shuffle=True, random_state=42)
rmse_list = []

for train_idx, valid_idx in kf.split(X, y):
    X_train, X_valid = X.iloc[train_idx], X.iloc[valid_idx]
    y_train, y_valid = y.iloc[train_idx], y.iloc[valid_idx]

    # 標準化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train.select_dtypes(include=[np.number]))
    X_valid_scaled = scaler.transform(X_valid.select_dtypes(include=[np.number]))

    # LightGBMのハイパーパラメータを手動で設定
    params = {
        'objective': 'regression',
        'metric': 'rmse',
        'boosting_type': 'gbdt',
        'learning_rate': 0.1,
        'num_leaves': 31,
        'max_depth': 7,
        'min_data_in_leaf': 20,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'lambda_l1': 1.0,
        'lambda_l2': 1.0,
        'verbose': -1
    }

    # LightGBMの訓練データセットを作成
    train_dataset = lgb.Dataset(X_train_scaled, label=y_train, free_raw_data=False)
    valid_dataset = lgb.Dataset(X_valid_scaled, label=y_valid, reference=train_dataset)

    # モデルの訓練
    model = lgb.train(
        params,
        train_dataset,
        valid_sets=[valid_dataset],
        callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(period=10)]
    )

    # 検証データに対して予測
    y_pred = model.predict(X_valid_scaled, num_iteration=model.best_iteration)

    # RMSEを計算
    rmse = mean_squared_error(y_valid, y_pred, squared=False)
    rmse_list.append(rmse)

# クロスバリデーションの平均RMSEを表示
print(f"Average RMSE: {np.mean(rmse_list)}")

# 特徴量重要度の取得と表示
importance = model.feature_importance(importance_type='gain')
feature_names = X.columns
for name, imp in sorted(zip(feature_names, importance), key=lambda x: x[1], reverse=True):
    print(f"Feature: {name}, Importance: {imp}")

# データ全体で予測
X_scaled_predict = scaler.transform(data_selected[feature_names].select_dtypes(include=[np.number]))
y_pred_lgb = np.expm1(model.predict(X_scaled_predict, num_iteration=model.best_iteration))
y_exp = np.expm1(y)

# 'Brand'ごとに評価するためにデータフレームに予測値と実測値を追加
data_selected['y_exp'] = y_exp
data_selected['y_pred_lgb'] = y_pred_lgb

# 'Brand'列のエンコードを元のカテゴリ値に戻す（元のブランド名に戻す）
if 'Brand_original' in data_selected.columns:
    data_selected['Brand'] = data_selected['Brand_original']
else:
    print("Error: 'Brand_original' column not found.")

# 差分を計算
data_selected['diff'] = data_selected['y_exp'] - data_selected['y_pred_lgb']

# 誤差率を計算
data_selected['diff_rate'] = data_selected['diff'] / data_selected['y_exp'] * 100  # パーセンテージ表示

# 誤差率のフィルタリング
filtered_results = data_selected[(data_selected['diff_rate'] >= -200) & (data_selected['diff_rate'] <= 200)]  # 例: -200%から200%の範囲

# 誤差率をプロット
plt.figure(figsize=(12, 6))
sns.histplot(filtered_results["diff_rate"], bins=1000, kde=True)
plt.title('Distribution of Prediction Error Rates (Actual - Predicted)')
plt.xlabel('Error Rate (%)')
plt.ylabel('Frequency')
plt.axvline(0, color='red', linestyle='--')  # 0の位置に縦線を引く
plt.show()

# 'Brand'ごとにMAPEを計算
def mean_absolute_percentage_error(y_true, y_pred):
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100

brand_mape = data_selected.groupby('Brand').apply(
    lambda x: mean_absolute_percentage_error(x['y_exp'], x['y_pred_lgb'])
)

# ブランドごとのデータ数とMAPEをリスト形式で表示
brand_counts = data_selected['Brand'].value_counts()
brand_mape_list = []
for brand in brand_counts.index:
    count = brand_counts[brand]
    mape = brand_mape[brand]
    brand_mape_list.append({'Brand': brand, 'Count': count, 'MAPE': mape})

# Countの大きい順にソートして表示
brand_mape_list_sorted_by_count = sorted(brand_mape_list, key=lambda x: x['Count'], reverse=True)

# 結果を表示
print("List of {Brand, Count, MAPE} sorted by Count:")
for entry in brand_mape_list_sorted_by_count:
    print(f"Brand: {entry['Brand']}, Count: {entry['Count']}, MAPE: {entry['MAPE']:.2f}%")

# 全体の評価指標の計算
rmse_final = mean_squared_error(y_exp, y_pred_lgb, squared=False)
mae_final = mean_absolute_error(y_exp, y_pred_lgb)
mape_final = mean_absolute_percentage_error(y_exp, y_pred_lgb)
print(f"Final RMSE with LightGBM model: {rmse_final}")
print(f"Final MAE with LightGBM model: {mae_final}")
print(f"Final MAPE with LightGBM model: {mape_final}%")