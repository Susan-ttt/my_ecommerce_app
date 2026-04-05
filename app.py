import streamlit as st
import requests
import json
import sys
import os
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import pandas as pd
from docx import Document

# 强制编码设置
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# 配置
DEEPSEEK_API_KEY = "你的真实密钥"
URL = "https://api.deepseek.com/v1/chat/completions"

st.set_page_config(page_title="电商评论分析看板", layout="wide")
st.title("📊 电商竞对评论区洞察看板")


# ========== 辅助函数 ==========
def call_ai_analysis(comments_list):
    if not comments_list:
        return None
    comments_text = "\n".join([f"{i + 1}. {c}" for i, c in enumerate(comments_list)])
    prompt = f"""你是一个电商运营专家。请分析以下用户评论，输出：
1. 高频正面关键词（出现次数最多的3-5个词，每个词附带出现次数）
2. 高频负面关键词（出现次数最多的3-5个词，每个词附带出现次数）
3. 总体运营优化建议（3条，具体可执行）

评论列表：
{comments_text}

请严格按照以下JSON格式输出，不要有其他内容：
{{
    "positive_keywords": [["词1", 次数], ["词2", 次数], ...],
    "negative_keywords": [["词1", 次数], ["词2", 次数], ...],
    "suggestions": ["建议1", "建议2", "建议3"]
}}
"""
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是电商运营专家，输出必须是合法JSON。"},
            {"role": "user", "content": prompt}
        ]
    }
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(body))
    }
    try:
        response = requests.post(URL, headers=headers, data=body, timeout=60)
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            try:
                data = json.loads(content)
            except:
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                else:
                    data = {"positive_keywords": [], "negative_keywords": [], "suggestions": ["解析失败"]}
            return data
        else:
            st.error(f"API调用失败：{response.text}")
            return None
    except Exception as e:
        st.error(f"请求异常：{e}")
        return None


def generate_wordcloud(keywords_dict, title):
    if not keywords_dict:
        return None
    font_path = 'C:/Windows/Fonts/simhei.ttf'
    if not os.path.exists(font_path):
        font_path = 'C:/Windows/Fonts/msyh.ttc'
    if not os.path.exists(font_path):
        font_path = None
    wc = WordCloud(width=800, height=400, background_color='white', font_path=font_path)
    wc.generate_from_frequencies(keywords_dict)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    ax.set_title(title, fontsize=16)
    return fig


# ========== 初始化 session_state ==========
if "step" not in st.session_state:
    st.session_state.step = "input"
if "comment_text" not in st.session_state:
    st.session_state.comment_text = ""
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

# ========== 导航按钮 ==========
col_nav1, col_nav2, _ = st.columns([1, 1, 4])
with col_nav1:
    if st.button("⬅️ 上一步（编辑输入）"):
        st.session_state.step = "input"
        st.rerun()
with col_nav2:
    if st.button("下一步 ➡️"):
        # 直接使用 comment_text 中的内容
        lines = st.session_state.comment_text.strip().split('\n')
        comments = [line.strip() for line in lines if line.strip()]
        if len(comments) == 0:
            st.warning("请先输入评论或上传文件")
        else:
            with st.spinner(f"正在分析 {len(comments)} 条评论..."):
                ai_data = call_ai_analysis(comments)
                if ai_data:
                    st.session_state.analysis_result = {
                        "comments_count": len(comments),
                        "positive": ai_data.get("positive_keywords", []),
                        "negative": ai_data.get("negative_keywords", []),
                        "suggestions": ai_data.get("suggestions", []),
                        "raw_comments": comments
                    }
                    report_text = f"电商评论分析报告\n\n共分析 {len(comments)} 条评论\n\n正面关键词：\n"
                    for word, cnt in st.session_state.analysis_result["positive"]:
                        report_text += f"  {word}: {cnt}次\n"
                    report_text += "\n负面关键词：\n"
                    for word, cnt in st.session_state.analysis_result["negative"]:
                        report_text += f"  {word}: {cnt}次\n"
                    report_text += "\n运营建议：\n"
                    for sug in st.session_state.analysis_result["suggestions"]:
                        report_text += f"  - {sug}\n"
                    st.session_state.analysis_result["report_text"] = report_text
                    st.session_state.step = "result"
                    st.rerun()
                else:
                    st.error("分析失败，请重试")

# ========== 输入界面 ==========
if st.session_state.step == "input":
    st.markdown("粘贴多条用户评论（每行一条），或上传文件（txt/csv/xlsx/docx），然后点击「下一步」进行分析。")

    with st.sidebar:
        st.header("📂 上传文件")
        uploaded_file = st.file_uploader("支持 .txt, .csv, .xlsx, .docx", type=["txt", "csv", "xlsx", "docx"])
        if uploaded_file is not None:
            content = ""
            try:
                if uploaded_file.name.endswith('.txt'):
                    content = uploaded_file.read().decode("utf-8")
                elif uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                    if df.shape[1] >= 1:
                        content = "\n".join(df.iloc[:, 0].astype(str).tolist())
                elif uploaded_file.name.endswith('.xlsx'):
                    df = pd.read_excel(uploaded_file, engine='openpyxl')
                    if df.shape[1] >= 1:
                        content = "\n".join(df.iloc[:, 0].astype(str).tolist())
                elif uploaded_file.name.endswith('.docx'):
                    doc = Document(uploaded_file)
                    content = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                if content:
                    st.session_state.comment_text = content
                    st.success(f"已加载 {uploaded_file.name}，共 {len(content.splitlines())} 行")
                    st.rerun()
                else:
                    st.warning("文件内容为空或无法解析")
            except Exception as e:
                st.error(f"读取文件失败：{e}")

    comment_text = st.text_area(
        "✏️ 评论内容（每条评论换行分隔）",
        value=st.session_state.comment_text,
        height=300,
        placeholder="例如：\n音质很好，但电池不耐用\n物流很快，包装破损\n客服态度好，回复及时"
    )
    # 同步用户编辑的内容到 session_state
    st.session_state.comment_text = comment_text

    if st.button("🗑️ 清空所有输入"):
        st.session_state.comment_text = ""
        st.rerun()

# ========== 结果界面 ==========
elif st.session_state.step == "result":
    if st.session_state.analysis_result is None:
        st.warning("没有分析结果，请先点击「下一步」进行分析。")
        if st.button("返回输入"):
            st.session_state.step = "input"
            st.rerun()
    else:
        res = st.session_state.analysis_result
        st.success(f"分析完成！共分析 {res['comments_count']} 条评论")

        if st.button("📥 下载报告"):
            report = res.get("report_text", "")
            if report:
                st.download_button("点击下载", data=report, file_name="评论分析报告.txt", mime="text/plain")

        colA, colB = st.columns(2)
        with colA:
            st.subheader("👍 高频正面关键词")
            if res["positive"]:
                pos_dict = {word: cnt for word, cnt in res["positive"]}
                st.table({"关键词": list(pos_dict.keys()), "出现次数": list(pos_dict.values())})
                fig_pos = generate_wordcloud(pos_dict, "正面关键词词云")
                if fig_pos:
                    st.pyplot(fig_pos)
            else:
                st.info("未检测到正面关键词")

        with colB:
            st.subheader("👎 高频负面关键词")
            if res["negative"]:
                neg_dict = {word: cnt for word, cnt in res["negative"]}
                st.table({"关键词": list(neg_dict.keys()), "出现次数": list(neg_dict.values())})
                fig_neg = generate_wordcloud(neg_dict, "负面关键词词云")
                if fig_neg:
                    st.pyplot(fig_neg)
            else:
                st.info("未检测到负面关键词")

        st.subheader("💡 运营优化建议")
        for i, sug in enumerate(res["suggestions"], 1):
            st.write(f"{i}. {sug}")