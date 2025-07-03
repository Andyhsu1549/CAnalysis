import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from PIL import Image
import os
import requests
import base64
from io import BytesIO
import numpy as np
import openai
import time
import plotly.io as pio
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib import colors

openai.api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")


# 去白底函數
def remove_white_background(img):
    img = img.convert("RGBA")
    data = np.array(img)
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    white_threshold = 240
    mask = (r > white_threshold) & (g > white_threshold) & (b > white_threshold)
    data[mask] = [255, 255, 255, 0]
    return Image.fromarray(data)

# 統一尺寸函數
def resize_with_padding(img, target_size=(500, 500)):
    img = img.convert("RGBA")
    old_size = img.size
    ratio = min(target_size[0] / old_size[0], target_size[1] / old_size[1])
    new_size = (int(old_size[0] * ratio), int(old_size[1] * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    new_img = Image.new("RGBA", target_size, (255, 255, 255, 0))
    paste_position = ((target_size[0] - new_size[0]) // 2, (target_size[1] - new_size[1]) // 2)
    new_img.paste(img, paste_position)
    return new_img

# ChatGPT 函數
def ask_chatgpt(prompt):
    client = openai.Client(api_key=openai.api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


# 頁面設定
st.set_page_config(page_title="INTENZA 競品分析工具", layout="wide")
st.title("💡 INTENZA 競品分析數位化轉型工具")


with st.sidebar.expander("📂 請上傳 CSV 檔案", expanded=False):
    uploaded_file = st.file_uploader("上傳", type=["csv"], label_visibility="collapsed")


if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    with st.expander("📄 原始資料表格（點擊展開/收合）", expanded=False):
        st.dataframe(df, use_container_width=True)

    numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns.tolist()
    non_numeric_columns = df.select_dtypes(exclude=['float64', 'int64']).columns.tolist()

    品牌_fix_map = {"LifeFitness": "Life Fitness", "TRUE": "True Fitness", "VISION": "Vision Fitness"}
    df["品牌"] = df["品牌"].replace(品牌_fix_map)

    品牌_logos = {
        "Life Fitness": "logos/LF.jpg",
        "Matrix": "logos/matrix.jpg",
        "Precor": "logos/PRECOR.jpg",
        "Technogym": "logos/TG.jpg",
        "True Fitness": "logos/true.jpg",
        "Vision Fitness": "logos/VISON.jpg"
    }

    df["label"] = df["產品型號"]
    model_options = (df["品牌"] + " - " + df["產品型號"]).drop_duplicates().tolist()

    st.sidebar.header("⚙️ 比較設定")
    selected_models = st.sidebar.multiselect("🏷️ 選擇最多 5 個品牌與機型", model_options, max_selections=5)
    selected_numeric_cols = st.sidebar.multiselect("📈 選擇要比較的數值欄位（可多選）", numeric_columns, default=numeric_columns[:1])

    chart_width, chart_height, bottom_margin = 900, 500, 170
    logo_sizey, logo_y_offset, product_img_sizey, product_img_y_offset = 0.14, -0.10, 0.30, -0.33

    chart_type_map = {}
    if selected_numeric_cols:
        with st.sidebar.expander("📐 圖表類型設定", expanded=True):
            for col in selected_numeric_cols:
                chart_type_map[col] = st.selectbox(f"圖表類型 - {col}", ["長條圖（Bar）", "折線圖（Line）", "散點圖（Scatter）"], key=f"{col}_chart")

    # 非數值欄位全選邏輯
    st.sidebar.write("📋 其他類別欄位選擇")
    all_text_cols = [col for col in non_numeric_columns if col not in ['品牌', '產品型號', 'label', '圖片網址']]
    select_all = st.sidebar.checkbox("全選")
    if select_all:
        selected_text_cols = st.sidebar.multiselect("選擇欄位", all_text_cols, default=all_text_cols)
    else:
        selected_text_cols = st.sidebar.multiselect("選擇欄位", all_text_cols)

    chart_width, chart_height, bottom_margin = 900, 500, 170
    logo_sizey, logo_y_offset, product_img_sizey, product_img_y_offset = 0.14, -0.10, 0.30, -0.33

    if selected_models:
        selected_品牌s = [x.split(" - ")[0] for x in selected_models]
        selected_products = [x.split(" - ")[1] for x in selected_models]
        filtered_df = df[df["品牌"].isin(selected_品牌s) & df["產品型號"].isin(selected_products)].drop_duplicates(subset=["品牌", "產品型號"])

        for col in selected_numeric_cols:
            chart_data = filtered_df[["label", "品牌", "產品型號", col, "圖片網址"]].copy()
            chart_data[col] = chart_data[col].fillna(0)
            chart_data = chart_data.sort_values(by=col)  # 排序
        
            st.subheader(f"📊 【{col}】比較圖（共 {len(chart_data)} 筆）")
        
            fig = go.Figure()
            chart_type = chart_type_map.get(col, "長條圖（Bar）")
        
            for 品牌 in chart_data["品牌"].unique():
                subset = chart_data[chart_data["品牌"] == 品牌]
        
                if chart_type == "長條圖（Bar）":
                    fig.add_trace(go.Bar(
                        x=subset["label"],
                        y=subset[col],
                        name=品牌,
                        text=subset[col],
                        textposition='outside',
                        textfont=dict(size=11)
                    ))
                elif chart_type == "折線圖（Line）":
                    fig.add_trace(go.Scatter(
                        x=subset["label"],
                        y=subset[col],
                        mode='lines+markers+text',
                        name=品牌,
                        text=subset[col],
                        textposition='top center',
                        textfont=dict(size=11)
                    ))
                elif chart_type == "散點圖（Scatter）":
                    fig.add_trace(go.Scatter(
                        x=subset["label"],
                        y=subset[col],
                        mode='markers+text',
                        name=品牌,
                        text=subset[col],
                        textposition='top center',
                        textfont=dict(size=11)
                    ))
        
            fig.update_layout(
                width=chart_width,
                height=chart_height,
                margin=dict(l=50, r=50, t=50, b=bottom_margin),
                xaxis=dict(categoryorder="array", categoryarray=chart_data["label"].tolist())
            )

        
            for _, row in chart_data.iterrows():
                label, 品牌 = row["label"], row["品牌"]
                logo_path = 品牌_logos.get(品牌)
                if logo_path and os.path.exists(logo_path):
                    img = Image.open(logo_path)
                    fig.add_layout_image(dict(
                        source=img, x=label, y=logo_y_offset,
                        xref="x", yref="paper",
                        sizex=1, sizey=logo_sizey,
                        xanchor="center", yanchor="top",
                        layer="above"
                    ))
        
            for _, row in chart_data.iterrows():
                label, img_url = row["label"], row["圖片網址"]
                if isinstance(img_url, str) and img_url.startswith("http"):
                    try:
                        img = Image.open(BytesIO(requests.get(img_url).content))
                        img = remove_white_background(img)
                        img = resize_with_padding(img)
                        buffer = BytesIO()
                        img.save(buffer, format="PNG")
                        img_base64 = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"
                        fig.add_layout_image(dict(
                            source=img_base64, x=label, y=product_img_y_offset,
                            xref="x", yref="paper",
                            sizex=1, sizey=product_img_sizey,
                            xanchor="center", yanchor="top",
                            layer="above"
                        ))
                    except:
                        pass
        
            st.plotly_chart(fig, use_container_width=True)

        st.write("")
        st.write("")
        st.write("")
        st.subheader("📋 非數值規格比較表格")
        
        # 重組資料
        filtered_df = filtered_df.reset_index(drop=True)
        transposed_data = []
        for spec in selected_text_cols:
            row = [spec]
            for _, product_row in filtered_df.iterrows():
                row.append(product_row[spec])
            transposed_data.append(row)
        
        # 表頭兩層
        brand_row = [""] + [row["品牌"] for _, row in filtered_df.iterrows()]
        model_row = ["規格名稱"] + [row["產品型號"] for _, row in filtered_df.iterrows()]
        
        st.markdown(f"""
        <style>
        .custom-table-container {{
            width: {chart_width}px;
            margin-left: auto;
            margin-right: auto;
        }}
        
        @media print {{
        
            .custom-table-container {{
                width: 100% !important;
            }}
        
            .plotly-graph-div {{
                width: 100% !important;
                max-width: 100% !important;
            }}
        
            .stApp {{
                width: 100% !important;
                max-width: 100% !important;
                overflow: visible !important;
            }}
        
            img {{
                max-width: 100% !important;
                height: auto !important;
            }}
        }}
        </style>
        """, unsafe_allow_html=True)


        
        # 組出 HTML 表格
        html = f"""
        <style>
        .custom-table-container {{
            width: {chart_width}px;
            margin-left: O;
            margin-right: auto;
        }}
        .custom-table {{
            border-collapse: collapse;
            width: 100%;
            table-layout: fixed;
        }}
        .custom-table th, .custom-table td {{
            border: none;
            padding: 8px;
            text-align: center;
            word-wrap: break-word;
            font-size: 14px;
        }}
        .custom-table th:first-child, .custom-table td:first-child {{
            width: 100px;
            color: rgb(245,245,245);
            font-weight: bold;
        }}
        .custom-table th {{
            color: rgb(188,188,188);
            font-weight: bold;
            background-color: transparent;
        }}
        .custom-table td {{
            color: rgb(188,188,188);
            background-color: transparent;
        }}
        </style>
        <div class="custom-table-container">
        <table class="custom-table">
        <thead>
        <tr>
        """
        
        # 第一層：品牌
        for col in brand_row:
            html += f"<th>{col}</th>"
        html += "</tr><tr>"
        
        # 第二層：型號
        for col in model_row:
            html += f"<th>{col}</th>"
        html += "</tr></thead><tbody>"
        
        # 資料內容
        for row in transposed_data:
            html += "<tr>"
            for cell in row:
                display = "-" if pd.isna(cell) or cell == "" else cell
                html += f"<td>{display}</td>"
            html += "</tr>"
        
        html += "</tbody></table></div>"
        
        st.markdown(html, unsafe_allow_html=True)



if uploaded_file is not None and selected_models and (selected_numeric_cols or selected_text_cols):
    
    st.write("---")
    st.subheader("🤖 ChatGPT 自動分析")

    compare_cols = ["品牌", "產品型號"] + selected_numeric_cols + selected_text_cols
    compare_df = filtered_df[compare_cols]

    # 初始化 session_state
    if "gpt_response" not in st.session_state:
        st.session_state["gpt_response"] = ""

    if st.button("請 ChatGPT 總結這次的比較結果"):
        prompt = f"""
以下為健身器材競品詳細比較資料，請嚴格依據資料客觀整理以下內容，並模擬專業報告的視覺層次，讓標題與內容在字體大小或排版上有清楚區分：

【數值型規格分析】
請逐一針對各項數值規格，提供以下資訊，標題請以加大、加粗格式呈現，內容則正常字級：
- 規格名稱
- 數值範圍（最小值 ~ 最大值）
- 具有最大值之品牌與型號
- 具有最小值之品牌與型號
以上內容請以清楚表格或條列方式呈現，禁止使用 Markdown 或符號，保持純文字。

【文字描述類規格分析】
針對各產品於文字描述類規格的差異，請逐項條列，規格名稱請加大、加粗，內容正常字級，語句工整，避免冗詞。

【SWOT分析（半商用健身房角度）】
每款產品請獨立製作「優勢」「劣勢」「機會」「威脅」四個表格，表格結構統一、簡潔，標題加粗顯示，內容正常字級，內容務必具體、避免抽象語言，在這邊的所有表格上下都要寬度對齊。

【競爭力規格設計建議】
條列具體特徵與設計參數，只給規格和數值，規格重點加粗，內容正常字級。

補充規範：
- 全程使用繁體中文
- 僅允許純文字、表格與條列，禁止任何 Markdown、特殊符號或英文半形標點
- 排版模擬A4專業報告，禁止過寬表格，過長文字請自動換行
- 請特別注意標題與內容的視覺層次感，模擬專業簡報或報告書中的格式差異

以下為本次重點規格：
{', '.join(selected_numeric_cols + selected_text_cols)}

資料如下：
{compare_df.to_string(index=False)}
"""

        with st.spinner("分析中..."):
            gpt_response = ask_chatgpt(prompt)
        
        # 暫存結果
        st.session_state["gpt_response"] = gpt_response

    # 若有暫存結果就顯示
    if st.session_state["gpt_response"]:
        st.write(st.session_state["gpt_response"])


    st.write("---")
    st.subheader("💬 ChatGPT 自由提問")
    user_question = st.text_input("請輸入您的問題")
    if st.button("送出問題"):
        if user_question.strip():
            with st.spinner("回覆中..."):
                st.write(ask_chatgpt(user_question))

elif uploaded_file is None:
    st.info("請上傳 CSV 檔案以開始。") 