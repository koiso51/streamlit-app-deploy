
import streamlit as st

st.title("サンプルアプリ①: 簡単なWebアプリ")

input_message = st.text_input(label="文字数のカウント対象となるテキストを入力してください。")

text_count = len(input_message)

if st.button("実行"):

    st.write(f"文字数: {text_count}")


