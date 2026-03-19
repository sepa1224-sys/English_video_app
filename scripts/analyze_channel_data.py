#!/usr/bin/env python3
"""
analyze_channel_data.py
気合イングリッシュ チャンネルデータの分析スクリプト（Priority 2）

出力:
  data/channel_analysis/analysis_report.md  — Claude共有用レポート
  data/channel_analysis/charts/             — 各種グラフ
"""

import os
import json
import csv
import re
from datetime import datetime, timezone
from collections import Counter, defaultdict
import math

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# ─────────────────────────────────────────────
# フォント設定（日本語）
# ─────────────────────────────────────────────
plt.rcParams["font.family"] = "Noto Sans CJK JP"
plt.rcParams["axes.unicode_minus"] = False

BASE_DIR   = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR   = os.path.join(BASE_DIR, "data", "channel_analysis")
CHART_DIR  = os.path.join(DATA_DIR, "charts")
CSV_PATH   = os.path.join(DATA_DIR, "kiiai_english_channel.csv")
JSON_PATH  = os.path.join(DATA_DIR, "kiiai_english_channel.json")
REPORT_OUT = os.path.join(DATA_DIR, "analysis_report.md")

os.makedirs(CHART_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# データ読み込み
# ─────────────────────────────────────────────
df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
df["published_date"] = df["published_at"].dt.date
df["year_month"] = df["published_at"].dt.to_period("M")
df["duration_min"] = df["duration_seconds"] / 60

print(f"[INFO] 動画数: {len(df)}")

# ─────────────────────────────────────────────
# カテゴリ分類
# ─────────────────────────────────────────────
def classify(title):
    t = title
    if "東大" in t or "リスニング" in t:
        return "東大リスニング"
    if "鉄壁" in t:
        return "鉄壁"
    if "ターゲット1900" in t or "1900" in t:
        return "ターゲット1900"
    if "ターゲット1400" in t or "1400" in t:
        return "ターゲット1400"
    if "ターゲット1200" in t or "1200" in t:
        return "ターゲット1200"
    if "LEAP" in t or "leap" in t.lower():
        return "LEAP"
    if "準1級" in t or "英検" in t:
        return "英検"
    if "コンセプト" in t or "紹介" in t:
        return "チャンネル紹介"
    return "その他"

df["category"] = df["title"].apply(classify)

# ─────────────────────────────────────────────
# 1. 再生数ランキング TOP10
# ─────────────────────────────────────────────
top10 = df.nlargest(10, "view_count")[["title", "view_count", "like_count", "comment_count", "duration_min", "published_at"]]
top10["published_at"] = top10["published_at"].dt.strftime("%Y-%m-%d")
top10["title_short"] = top10["title"].str[:35]

fig, ax = plt.subplots(figsize=(12, 6))
bars = ax.barh(range(len(top10)), top10["view_count"].values, color="#FF6B6B", edgecolor="white")
ax.set_yticks(range(len(top10)))
ax.set_yticklabels(top10["title_short"].values, fontsize=9)
ax.invert_yaxis()
ax.set_xlabel("再生数")
ax.set_title("再生数 TOP10 動画", fontsize=14, fontweight="bold")
for i, (bar, val) in enumerate(zip(bars, top10["view_count"].values)):
    ax.text(bar.get_width() + 200, bar.get_y() + bar.get_height()/2,
            f"{val:,}", va="center", fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(CHART_DIR, "01_top10_views.png"), dpi=150, bbox_inches="tight")
plt.close()
print("[OK] グラフ1: TOP10再生数")

# ─────────────────────────────────────────────
# 2. カテゴリ別 平均再生数
# ─────────────────────────────────────────────
cat_stats = df.groupby("category").agg(
    avg_views=("view_count", "mean"),
    total_views=("view_count", "sum"),
    count=("video_id", "count"),
    avg_likes=("like_count", "mean"),
).sort_values("avg_views", ascending=False)

fig, ax = plt.subplots(figsize=(10, 5))
colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F"]
bars = ax.bar(cat_stats.index, cat_stats["avg_views"], color=colors[:len(cat_stats)], edgecolor="white", linewidth=1.5)
ax.set_xlabel("カテゴリ")
ax.set_ylabel("平均再生数")
ax.set_title("カテゴリ別 平均再生数", fontsize=14, fontweight="bold")
ax.tick_params(axis="x", rotation=30)
for bar, val in zip(bars, cat_stats["avg_views"]):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 100,
            f"{val:,.0f}", ha="center", va="bottom", fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(CHART_DIR, "02_category_avg_views.png"), dpi=150, bbox_inches="tight")
plt.close()
print("[OK] グラフ2: カテゴリ別平均再生数")

# ─────────────────────────────────────────────
# 3. 動画長と再生数の散布図
# ─────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 6))
scatter = ax.scatter(df["duration_min"], df["view_count"],
                     c=df["category"].astype("category").cat.codes,
                     cmap="tab10", alpha=0.7, s=80, edgecolors="white", linewidth=0.5)
ax.set_xlabel("動画長（分）")
ax.set_ylabel("再生数")
ax.set_title("動画長 vs 再生数", fontsize=14, fontweight="bold")
# カテゴリ凡例
categories = df["category"].unique()
handles = [plt.scatter([], [], c=plt.cm.tab10(i/len(categories)), s=60, label=cat)
           for i, cat in enumerate(categories)]
ax.legend(handles=handles, loc="upper right", fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(CHART_DIR, "03_duration_vs_views.png"), dpi=150, bbox_inches="tight")
plt.close()
print("[OK] グラフ3: 動画長vs再生数")

# ─────────────────────────────────────────────
# 4. 月別投稿数と累計再生数
# ─────────────────────────────────────────────
monthly = df.groupby("year_month").agg(
    count=("video_id", "count"),
    total_views=("view_count", "sum"),
).reset_index()
monthly["year_month_str"] = monthly["year_month"].astype(str)

fig, ax1 = plt.subplots(figsize=(12, 5))
ax2 = ax1.twinx()
ax1.bar(range(len(monthly)), monthly["count"], color="#4ECDC4", alpha=0.8, label="投稿数")
ax2.plot(range(len(monthly)), monthly["total_views"], color="#FF6B6B", marker="o", linewidth=2, label="月間再生数")
ax1.set_xticks(range(len(monthly)))
ax1.set_xticklabels(monthly["year_month_str"], rotation=45, ha="right", fontsize=8)
ax1.set_ylabel("投稿数", color="#4ECDC4")
ax2.set_ylabel("月間再生数", color="#FF6B6B")
ax1.set_title("月別 投稿数 & 月間再生数", fontsize=14, fontweight="bold")
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
plt.tight_layout()
plt.savefig(os.path.join(CHART_DIR, "04_monthly_posts_views.png"), dpi=150, bbox_inches="tight")
plt.close()
print("[OK] グラフ4: 月別投稿数・再生数")

# ─────────────────────────────────────────────
# 5. 動画長の分布ヒストグラム
# ─────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
ax.hist(df["duration_min"], bins=15, color="#45B7D1", edgecolor="white", linewidth=1.2)
ax.set_xlabel("動画長（分）")
ax.set_ylabel("動画数")
ax.set_title("動画長の分布", fontsize=14, fontweight="bold")
ax.axvline(df["duration_min"].median(), color="#FF6B6B", linestyle="--", linewidth=2, label=f"中央値: {df['duration_min'].median():.1f}分")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(CHART_DIR, "05_duration_distribution.png"), dpi=150, bbox_inches="tight")
plt.close()
print("[OK] グラフ5: 動画長分布")

# ─────────────────────────────────────────────
# 6. いいね率（いいね/再生数）TOP10
# ─────────────────────────────────────────────
df_with_views = df[df["view_count"] > 100].copy()
df_with_views["like_rate"] = df_with_views["like_count"] / df_with_views["view_count"] * 100
top_like = df_with_views.nlargest(10, "like_rate")[["title", "like_rate", "view_count", "like_count"]]
top_like["title_short"] = top_like["title"].str[:35]

fig, ax = plt.subplots(figsize=(12, 6))
bars = ax.barh(range(len(top_like)), top_like["like_rate"].values, color="#96CEB4", edgecolor="white")
ax.set_yticks(range(len(top_like)))
ax.set_yticklabels(top_like["title_short"].values, fontsize=9)
ax.invert_yaxis()
ax.set_xlabel("いいね率（%）")
ax.set_title("いいね率 TOP10（再生数100以上）", fontsize=14, fontweight="bold")
for bar, val in zip(bars, top_like["like_rate"].values):
    ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
            f"{val:.2f}%", va="center", fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(CHART_DIR, "06_like_rate_top10.png"), dpi=150, bbox_inches="tight")
plt.close()
print("[OK] グラフ6: いいね率TOP10")

# ─────────────────────────────────────────────
# 統計サマリー計算
# ─────────────────────────────────────────────
total_views = df["view_count"].sum()
avg_views   = df["view_count"].mean()
median_views = df["view_count"].median()
max_views   = df["view_count"].max()
max_video   = df.loc[df["view_count"].idxmax(), "title"]
avg_duration = df["duration_min"].mean()
median_duration = df["duration_min"].median()

# 投稿頻度
date_range_days = (df["published_at"].max() - df["published_at"].min()).days
posts_per_month = len(df) / (date_range_days / 30) if date_range_days > 0 else 0

# 高再生数動画（5000再生以上）の特徴
high_view = df[df["view_count"] >= 5000]
low_view  = df[df["view_count"] < 1000]

# タイトルパターン分析
bracket_pattern = df["title"].str.contains(r"【.*?】", regex=True).sum()
number_pattern  = df["title"].str.contains(r"\d+〜\d+|No\.\d+|第\d+回", regex=True).sum()

# ─────────────────────────────────────────────
# Markdown レポート生成
# ─────────────────────────────────────────────
report = f"""# 気合イングリッシュ チャンネル分析レポート（Priority 2）

> **Claudeへの分析依頼**: 以下のデータを基に、チャンネル改善提案をお願いします。
> 分析観点: ①再生数が伸びている動画のパターン ②最適な動画長・投稿頻度 ③タイトル・サムネイルの傾向

---

## 1. チャンネル全体サマリー

| 指標 | 値 |
|---|---|
| 総動画数 | {len(df)} 件 |
| 総再生数 | {total_views:,} 回 |
| 平均再生数 | {avg_views:,.0f} 回 |
| 中央値再生数 | {median_views:,.0f} 回 |
| 最大再生数 | {max_views:,} 回 |
| 最多再生動画 | {max_video[:50]}... |
| 平均動画長 | {avg_duration:.1f} 分 |
| 中央値動画長 | {median_duration:.1f} 分 |
| 投稿期間 | {df['published_at'].min().strftime('%Y-%m-%d')} 〜 {df['published_at'].max().strftime('%Y-%m-%d')} |
| 月平均投稿数 | {posts_per_month:.1f} 本/月 |

---

## 2. 再生数 TOP10 動画

| # | タイトル | 公開日 | 再生数 | いいね | コメント | 動画長(分) |
|---|---|---|---|---|---|---|
"""

for i, (_, row) in enumerate(top10.iterrows(), 1):
    report += f"| {i} | {row['title'][:45]} | {row['published_at']} | {row['view_count']:,} | {row['like_count']:,} | {row['comment_count']:,} | {row['duration_min']:.0f} |\n"

report += f"""
---

## 3. カテゴリ別パフォーマンス

| カテゴリ | 動画数 | 平均再生数 | 合計再生数 | 平均いいね |
|---|---|---|---|---|
"""

for cat, row in cat_stats.iterrows():
    report += f"| {cat} | {int(row['count'])} | {row['avg_views']:,.0f} | {int(row['total_views']):,} | {row['avg_likes']:.1f} |\n"

report += f"""
---

## 4. 動画長別パフォーマンス分析

| 動画長 | 動画数 | 平均再生数 | 代表例 |
|---|---|---|---|
"""

bins = [(0, 5), (5, 15), (15, 30), (30, 60), (60, 9999)]
bin_labels = ["〜5分", "5〜15分", "15〜30分", "30〜60分", "60分以上"]
for (lo, hi), label in zip(bins, bin_labels):
    subset = df[(df["duration_min"] >= lo) & (df["duration_min"] < hi)]
    if len(subset) > 0:
        example = subset.nlargest(1, "view_count").iloc[0]["title"][:30]
        report += f"| {label} | {len(subset)} | {subset['view_count'].mean():,.0f} | {example}... |\n"

report += f"""
---

## 5. 月別投稿状況

| 年月 | 投稿数 | 月間再生数 |
|---|---|---|
"""

for _, row in monthly.iterrows():
    report += f"| {row['year_month_str']} | {int(row['count'])} | {int(row['total_views']):,} |\n"

report += f"""
---

## 6. タイトルパターン分析

| パターン | 使用率 |
|---|---|
| 【】括弧タイトル | {bracket_pattern}/{len(df)} ({bracket_pattern/len(df)*100:.0f}%) |
| 範囲・番号表記（例: 1〜500, No.1） | {number_pattern}/{len(df)} ({number_pattern/len(df)*100:.0f}%) |

### 高再生数動画（5,000回以上）の共通点

高再生数動画数: **{len(high_view)} 件**

"""

if len(high_view) > 0:
    report += "| タイトル | 再生数 | 動画長(分) | カテゴリ |\n|---|---|---|---|\n"
    for _, row in high_view.sort_values("view_count", ascending=False).iterrows():
        report += f"| {row['title'][:45]} | {row['view_count']:,} | {row['duration_min']:.0f} | {row['category']} |\n"

report += f"""
---

## 7. 全動画データ一覧

| video_id | タイトル | 公開日 | 再生数 | いいね | コメント | 動画長(秒) | カテゴリ |
|---|---|---|---|---|---|---|---|
"""

for _, row in df.sort_values("view_count", ascending=False).iterrows():
    report += f"| {row['video_id']} | {row['title'][:40]} | {str(row['published_at'])[:10]} | {row['view_count']:,} | {row['like_count']:,} | {row['comment_count']:,} | {row['duration_seconds']} | {row['category']} |\n"

report += f"""
---

## 8. Claudeへの分析依頼事項

以下の観点でチャンネル改善提案をお願いします：

1. **再生数が伸びている動画のパターン**
   - 鉄壁シリーズが圧倒的に強い理由の分析
   - 東大リスニングシリーズが伸び悩んでいる原因と改善策

2. **最適な動画長・投稿頻度**
   - 再生数との相関から見た最適な動画長
   - 月別投稿数と再生数の関係から見た最適投稿頻度

3. **タイトル・サムネイルの傾向分析**
   - 高再生数動画のタイトル構造の共通点
   - 改善が見込めるタイトルパターンの提案

4. **次に作るべきコンテンツの優先順位**
   - データドリブンな次回作の推薦

---
*分析実行日: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}*
*データ取得日: 2026-03-19*
*総動画数: {len(df)} 件*
"""

with open(REPORT_OUT, "w", encoding="utf-8") as f:
    f.write(report)

print(f"[OK] レポート保存: {REPORT_OUT}")
print("\n=== 分析完了 ===")
print(f"総動画数: {len(df)}")
print(f"総再生数: {total_views:,}")
print(f"平均再生数: {avg_views:,.0f}")
print(f"最多再生: {max_video[:50]} ({max_views:,}回)")
print(f"月平均投稿: {posts_per_month:.1f}本")
