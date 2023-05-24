import streamlit as st
import boto3
import requests
import json
import datetime
import os

import pandas as pd

import sqlite3

import plotly.graph_objects as go

# Streamlitのデフォルトのスタイルを無効にする
st.set_page_config(  # 全体の設定
    page_title="YoutubeStreamerComments",  # タイトル
    page_icon=None,  # アイコン（Noneで非表示）
    layout="wide",  # レイアウト
    initial_sidebar_state="expanded",  # サイドバーの初期状態
)

hide_footer_style = """
    <style>
    footer {
        visibility: hidden;
    }
    </style>
"""
st.markdown(hide_footer_style, unsafe_allow_html=True)

# CSSを使用してDataFrameを表示
st.markdown("""
    <style>
        .dataframe th {
            background-color: #f2f2f2;
        }
        .dataframe td {
            background-color: #ffffff;
        }
    </style>
    """, unsafe_allow_html=True)


# TODO implement
s3 = boto3.client('s3')

S3_BUCKET = "streamer-review"
SQLITE_FILE = "streamer_db.sqlite"


s3.download_file(S3_BUCKET, SQLITE_FILE, SQLITE_FILE)

#データベースに接続
filepath = SQLITE_FILE
conn = sqlite3.connect(filepath)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


st.title("Streamlit_cloud_配信者コメント検索")

st.text("配信者選択、検索キーワードを入力して検索すると\nAPIgatewayを経由して\nlambdaプログラムで\nlightsailに設置したqdrantからベクトル検索、meilisearchから全文検索")

# 検索可能なデータセット一覧取得
collection_list = []
# データベースから取得
cur.execute("""SELECT streamer_name, streamer_comment_data_youtube, streamer_comment_data_dataset_5ch FROM streamer_datasets""")
datasets_list = cur.fetchall()


for dataset in datasets_list:
    # youtube,5chどちらかのデータセットがあれば選択肢表示
    if dataset['streamer_comment_data_youtube'] is not None or dataset['streamer_comment_data_dataset_5ch'] is not None:
        collection_list.append(dataset['streamer_name'])


# プルダウンリストと検索ボックスを表示する
selected_streamer_name = st.selectbox("検索したい配信者を選択してください", collection_list)
search_word = st.text_input("検索するワードを入力してください。")
number_input1, number_input2 = st.columns(2)
with number_input1:
    result_limit = st.number_input("表示件数", 5, 500, 10)
with number_input2:
    threshold = st.number_input("閾値", 0.60, 0.99, 0.70)

flgCheck_date = st.checkbox('日付指定して検索')
if flgCheck_date:
    col1, col2, col3, col4, col5 = st.columns(5)
    # 日付指定
    with col1:
        start_date = st.date_input('開始日時',
                          min_value=datetime.date(2022, 1, 1),
                          max_value=datetime.date.today(),
                          value=datetime.date.today()
                        )
    with col2:
        start_time = st.time_input('', datetime.time(0, 0))
    with col3:
        st.write("<div style='display: flex; justify-content: center; align-items: center; margin-top: 40px;'>～</div>", unsafe_allow_html=True)
    with col4:
        end_date = st.date_input('終了日時',
                      min_value=datetime.date(2022, 1, 1),
                      max_value=datetime.date.today(),
                      value=datetime.date.today()
                    )
    with col5:
        end_time = st.time_input('', datetime.time(23, 59))
    st.container().markdown(
        """
        <style>
        .stDateInput>div {
            display: flex;
            align-items: center;
        }
        .stDateInput>div>div {
            flex-grow: 1;
            margin-right: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# 検索ボタン押した時
if st.button("検索"):
    if search_word and len(datasets_list) > 0:
        st.write("選択した配信者＞",selected_streamer_name)
        st.write("検索ワード＞",search_word)
        st.write("表示件数＞",result_limit)
        st.write("閾値＞",threshold)
        start_dt_unix = 0
        end_dt_unix = 0
        if flgCheck_date:
            start_dt = datetime.datetime.combine(start_date, start_time)
            end_dt = datetime.datetime.combine(end_date, end_time)
            st.write("書き込み期間範囲指定＞",start_dt,"から",end_dt,"まで")
            # unix化 JTCのままなので9時間引く
            start_dt_unix = int(start_dt.timestamp()) - (9 * 60 * 60)
            end_dt_unix = int(end_dt.timestamp()) - (9 * 60 * 60)
        
        myobj = {"streamer_name": selected_streamer_name,
                 "search_word": search_word,
                 "result_limit": result_limit,
                 "threshold": threshold,
                 "start_dt_unix": start_dt_unix,
                 "end_dt_unix": end_dt_unix
                 }
        # リクエストヘッダー
        headers = {'Content-Type': 'application/json'}
        
        # ベクトル検索用API
        url = os.environ['REST_API_URL']
        
        vector_search_res = requests.post(url, data = json.dumps(myobj), headers=headers)
        vector_search_res_json = json.loads(vector_search_res.text)
        
        comment_youtube_search_result = ""
        if vector_search_res_json["comment_youtube"] != "":
            comment_youtube_search_result = json.loads(vector_search_res_json["comment_youtube"])
        
        comment_5ch_search_result = ""
        if vector_search_res_json["comment_5ch"] != "":
            comment_5ch_search_result = json.loads(vector_search_res_json["comment_5ch"])
        
        comment_5ch_thread_title = vector_search_res_json["comment_5ch_thread"]
        
        if comment_youtube_search_result != "":
            st.write("【youtubeコメントからの検索】")
            df_y = pd.DataFrame(comment_youtube_search_result)
            st.dataframe(df_y)
            
            #st.dataframe( comment_youtube_search_result )
            
            # DataFrameの作成
            df_y = pd.DataFrame(comment_youtube_search_result)

            # datetime列を日時型に変換
            df_y['datetime'] = pd.to_datetime(df_y['datetime'])

            # 日付別にグループ化してカウント
            daily_counts = df_y.groupby(df_y['datetime'].dt.hour).size().reset_index(name='count')
            
            # Plotlyの棒グラフを作成
            fig = go.Figure(data=[go.Bar(x=daily_counts['datetime'], y=daily_counts['count'])])

            # グラフのレイアウト設定
            fig.update_layout(
                xaxis=dict(title='Date'),
                yaxis=dict(title='Count'),
            )

            # Plotlyの棒グラフをStreamlitで表示
            st.plotly_chart(fig)

        
        if comment_5ch_search_result != "":
            st.write("【5ch書き込みからの検索】")
            st.dataframe( comment_5ch_search_result )
            
            # DataFrameの作成
            df_5 = pd.DataFrame(comment_5ch_search_result)

            # datetime列を日時型に変換
            df_5['datetime'] = pd.to_datetime(df_5['datetime'])

            # 日付別にグループ化してカウント
            daily_counts = df_5.groupby(df_5['datetime'].dt.hour).size().reset_index(name='count')
            
            # Plotlyの棒グラフを作成
            fig = go.Figure(data=[go.Bar(x=daily_counts['datetime'], y=daily_counts['count'])])

            # グラフのレイアウト設定
            fig.update_layout(
                xaxis=dict(title='Date'),
                yaxis=dict(title='Count'),
            )

            # Plotlyの棒グラフをStreamlitで表示
            st.plotly_chart(fig)
            
            st.write("引用元：",comment_5ch_thread_title)
        
        
        
        #st.text(vector_search_res.text)