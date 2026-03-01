"""
週次テクノロジーニュースレポート自動生成スクリプト

毎週土曜日 12:00 JST に GitHub Actions から実行され、
20以上のテクノロジーメディアの RSS フィードを収集・分析して
ビジネスエグゼクティブ向けの日本語レポートを生成します。
"""

import re
import os
import feedparser
import anthropic
import pytz
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path

# 日本標準時
JST = pytz.timezone("Asia/Tokyo")

# ==============================================================================
# RSSフィード一覧（20以上のソース）
# ==============================================================================
RSS_FEEDS = [
    # --- 英語メディア（総合テック） ---
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "lang": "en", "category": "総合"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "lang": "en", "category": "総合"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "lang": "en", "category": "総合"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "lang": "en", "category": "総合"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/feed/", "lang": "en", "category": "総合"},
    {"name": "The Next Web", "url": "https://thenextweb.com/feed/", "lang": "en", "category": "総合"},
    {"name": "SiliconANGLE", "url": "https://siliconangle.com/feed/", "lang": "en", "category": "総合"},
    # --- 英語メディア（AI・研究） ---
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "lang": "en", "category": "AI・研究"},
    {"name": "IEEE Spectrum", "url": "https://spectrum.ieee.org/feeds/feed.rss", "lang": "en", "category": "AI・研究"},
    {"name": "AI News", "url": "https://artificialintelligence-news.com/feed/", "lang": "en", "category": "AI・研究"},
    # --- 英語メディア（エンタープライズ・ビジネス） ---
    {"name": "ZDNet", "url": "https://www.zdnet.com/news/rss.xml", "lang": "en", "category": "エンタープライズ"},
    {"name": "Computerworld", "url": "https://www.computerworld.com/index.rss", "lang": "en", "category": "エンタープライズ"},
    {"name": "TechRepublic", "url": "https://www.techrepublic.com/rssfeeds/articles/", "lang": "en", "category": "エンタープライズ"},
    {"name": "InfoQ", "url": "https://feed.infoq.com/", "lang": "en", "category": "エンタープライズ"},
    {"name": "SD Times", "url": "https://sdtimes.com/feed/", "lang": "en", "category": "エンタープライズ"},
    # --- 英語メディア（セキュリティ） ---
    {"name": "Dark Reading", "url": "https://www.darkreading.com/rss.xml", "lang": "en", "category": "セキュリティ"},
    {"name": "The Register", "url": "https://www.theregister.com/headlines.atom", "lang": "en", "category": "セキュリティ"},
    # --- 英語メディア（開発者・コミュニティ） ---
    {"name": "Hacker News", "url": "https://news.ycombinator.com/rss", "lang": "en", "category": "開発者"},
    {"name": "CNET", "url": "https://www.cnet.com/rss/news/", "lang": "en", "category": "開発者"},
    # --- 企業公式ブログ ---
    {"name": "Google AI Blog", "url": "https://blog.google/technology/ai/rss/", "lang": "en", "category": "企業ブログ"},
    {"name": "Microsoft Tech Blog", "url": "https://blogs.microsoft.com/feed/", "lang": "en", "category": "企業ブログ"},
    {"name": "AWS News Blog", "url": "https://aws.amazon.com/blogs/aws/feed/", "lang": "en", "category": "企業ブログ"},
    # --- 日本語メディア ---
    {"name": "ITmedia", "url": "https://rss.itmedia.co.jp/rss/2.0/itmedia_all.xml", "lang": "ja", "category": "日本語"},
    {"name": "ASCII.jp テクノロジー", "url": "https://ascii.jp/rss.xml", "lang": "ja", "category": "日本語"},
    {"name": "Publickey", "url": "https://www.publickey1.jp/atom.xml", "lang": "ja", "category": "日本語"},
]


def clean_html(text: str) -> str:
    """HTMLタグを除去してプレーンテキストに変換する。"""
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def fetch_articles(days_back: int = 7, max_per_feed: int = 5) -> list[dict]:
    """
    全RSSフィードから直近 days_back 日間の記事を収集する。

    Args:
        days_back: 何日前までの記事を収集するか（デフォルト7日）
        max_per_feed: 1フィードあたりの最大取得件数（デフォルト5件）

    Returns:
        記事情報の辞書リスト
    """
    cutoff = datetime.now(pytz.utc) - timedelta(days=days_back)
    articles = []

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            count = 0
            for entry in feed.entries:
                if count >= max_per_feed:
                    break

                # 公開日時を取得
                pub_date = None
                for date_field in ("published_parsed", "updated_parsed"):
                    parsed = getattr(entry, date_field, None)
                    if parsed:
                        pub_date = datetime(*parsed[:6], tzinfo=pytz.utc)
                        break

                # 取得期間外の記事をスキップ
                if pub_date and pub_date < cutoff:
                    continue

                summary = clean_html(getattr(entry, "summary", ""))[:600]

                articles.append(
                    {
                        "source": feed_info["name"],
                        "lang": feed_info["lang"],
                        "category": feed_info["category"],
                        "title": clean_html(entry.get("title", "")),
                        "link": entry.get("link", ""),
                        "summary": summary,
                        "date": pub_date.astimezone(JST).strftime("%Y-%m-%d") if pub_date else "不明",
                    }
                )
                count += 1

        except Exception as e:
            print(f"  [警告] {feed_info['name']} の取得に失敗しました: {e}")

    return articles


def build_prompt(articles: list[dict], report_date: str, week_range: str) -> str:
    """Claude へのプロンプトを構築する。"""
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += (
            f"\n【記事{i}】\n"
            f"- メディア: {a['source']} ({a['lang']}) /{a['category']}\n"
            f"- タイトル: {a['title']}\n"
            f"- 日付: {a['date']}\n"
            f"- 概要: {a['summary']}\n"
            f"- URL: {a['link']}\n"
        )

    source_list = "、".join(sorted({a["source"] for a in articles}))

    return f"""あなたはテクノロジー業界の優秀なジャーナリストです。
以下の直近1週間（{week_range}）に収集したテクノロジーニュース記事を分析し、
ビジネスエグゼクティブ向けの週次レポートを日本語で作成してください。

【収集記事一覧】
{articles_text}

【参照したメディア】
{source_list}

【レポート要件】
- 対象読者: 経営層・ビジネスエグゼクティブ（技術的な専門知識は前提としない）
- 各トピックには「ビジネスへの示唆」を必ず含める
- 業界横断的な視点でトレンドを整理する
- 具体的な企業名・製品名・数値を積極的に引用する
- 客観的かつ中立的なトーンで記述する

以下のフォーマットで、マークダウン形式のレポートを作成してください。

---

# 週次テクノロジートレンドレポート

**レポート日**: {report_date}
**対象期間**: {week_range}
**参照メディア数**: {len(RSS_FEEDS)} 以上
**分析記事数**: {len(articles)} 件

---

## エグゼクティブサマリー

> 今週のテクノロジー動向を一段落で総括してください。

**今週の重要トレンド（Top 5）**

1. ...
2. ...
3. ...
4. ...
5. ...

---

## 主要トレンド詳細

### 1. [トレンド名]

**背景・概要**
...

**今週の主な動き**
- ...
- ...

**ビジネスへの示唆**
...

**関連記事**
- [記事タイトル](URL)

---

### 2. [トレンド名]
（同様のフォーマットで 5〜7 トレンドを記述）

---

## 注目の企業・製品動向

| 企業/製品 | 動向 | ビジネス的意味 |
|-----------|------|----------------|
| ...       | ...  | ...            |

---

## 今後の注目ポイント

来週以降、以下の動向・イベントに注目してください。

- **[日付/時期]**: ...
- **[日付/時期]**: ...

---

## 参照メディア一覧

{source_list}

---
*本レポートは AI によって自動生成されました。*
"""


def generate_report(articles: list[dict], report_date: str, week_range: str) -> str:
    """Claude API を使ってレポートを生成する。"""
    client = anthropic.Anthropic()
    prompt = build_prompt(articles, report_date, week_range)

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def save_report(content: str, date_str: str) -> Path:
    """レポートを reports/ ディレクトリに保存する。"""
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    filepath = reports_dir / f"{date_str}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def main() -> None:
    print("=" * 60)
    print("週次テクノロジーニュースレポート生成スクリプト")
    print("=" * 60)

    # 日時情報
    now_jst = datetime.now(JST)
    report_date = now_jst.strftime("%Y年%m月%d日（%A）")
    date_str = now_jst.strftime("%Y-%m-%d")
    week_start = (now_jst - timedelta(days=7)).strftime("%Y年%m月%d日")
    week_end = now_jst.strftime("%Y年%m月%d日")
    week_range = f"{week_start} 〜 {week_end}"

    print(f"\nレポート日    : {report_date}")
    print(f"対象期間      : {week_range}")
    print(f"参照フィード数: {len(RSS_FEEDS)} ソース")

    # 1. 記事収集
    print("\n[1/3] ニュース記事を収集中...")
    articles = fetch_articles(days_back=7, max_per_feed=5)
    print(f"      → {len(articles)} 件の記事を収集しました")

    if not articles:
        print("記事が見つかりませんでした。処理を終了します。")
        return

    # 2. レポート生成
    print("\n[2/3] Claude API でレポートを生成中...")
    report_content = generate_report(articles, report_date, week_range)
    print("      → レポート生成完了")

    # 3. 保存
    print("\n[3/3] レポートを保存中...")
    report_file = save_report(report_content, date_str)
    print(f"      → {report_file} に保存しました")

    print("\n" + "=" * 60)
    print("レポート生成が完了しました")
    print("=" * 60)
    print()
    print(report_content)


if __name__ == "__main__":
    main()
