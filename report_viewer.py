"""
週次テクノロジーニュースレポート ビューワー

reports/ ディレクトリに保存されたレポートを
Streamlit UI で閲覧できるアプリです。
"""

import streamlit as st
from pathlib import Path
from datetime import datetime

REPORTS_DIR = Path("reports")

st.set_page_config(
    page_title="週次テクノロジーニュースレポート",
    page_icon="📰",
    layout="wide",
)

st.title("📰 週次テクノロジーニュースレポート")
st.caption("ビジネスエグゼクティブ向け・毎週土曜日 12:00 JST 自動更新")

# レポートファイル一覧を取得（新しい順）
report_files = sorted(REPORTS_DIR.glob("*.md"), reverse=True) if REPORTS_DIR.exists() else []

if not report_files:
    st.info(
        "レポートがまだ生成されていません。\n\n"
        "GitHub Actions のワークフローが毎週土曜日 12:00 JST に自動実行されます。\n"
        "手動実行は GitHub リポジトリの **Actions** タブから行えます。"
    )
    st.stop()

# サイドバー: レポート選択
with st.sidebar:
    st.header("レポート一覧")
    selected_file = st.selectbox(
        "表示するレポートを選択",
        options=report_files,
        format_func=lambda p: p.stem,  # YYYY-MM-DD 形式
    )
    st.divider()
    st.metric("蓄積レポート数", f"{len(report_files)} 週分")

    if report_files:
        latest = report_files[0].stem
        oldest = report_files[-1].stem
        st.caption(f"最新: {latest}")
        st.caption(f"最古: {oldest}")

# メインエリア: レポート表示
if selected_file:
    content = selected_file.read_text(encoding="utf-8")

    # ダウンロードボタン
    col1, col2 = st.columns([8, 2])
    with col2:
        st.download_button(
            label="📥 Markdown ダウンロード",
            data=content,
            file_name=selected_file.name,
            mime="text/markdown",
        )

    st.divider()
    st.markdown(content)
