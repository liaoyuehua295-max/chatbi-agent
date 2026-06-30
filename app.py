import os
import streamlit as st
from dotenv import load_dotenv
from multi_agent import run as multi_agent_run
from agent import ChatBIAgent
from logger import log_query, update_feedback

load_dotenv()
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")

st.set_page_config(page_title="医疗众筹 ChatBI", page_icon="📊", layout="wide")
st.title("📊 医疗众筹 ChatBI Agent")
st.caption("基于 LangGraph 多智能体 + RAG + Text-to-SQL 的医疗众筹数据分析助手")

with st.sidebar:
    st.header("⚙️ 配置")
    user_name = st.text_input("👤 你的名字", value=st.session_state.get("user_name", ""), placeholder="输入姓名或昵称")
    if user_name:
        st.session_state["user_name"] = user_name
    model = st.selectbox("模型", ["qwen-plus", "qwen-turbo", "qwen-max"])
    enable_insight = st.toggle("💡 智能洞察分析", value=True, help="开启后每次查询自动生成异常识别和归因分析")

    if "agent" not in st.session_state:
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        st.session_state["agent"] = ChatBIAgent(DASHSCOPE_API_KEY, base_url, model, LANGCHAIN_API_KEY or None)

    if st.button("重置Agent", type="primary"):
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        st.session_state["agent"] = ChatBIAgent(DASHSCOPE_API_KEY, base_url, model, LANGCHAIN_API_KEY or None)
        st.success("已重置")

    if st.button("🗑️ 清空对话", key="clear_btn"):
        st.session_state["messages"] = []
        if "agent" in st.session_state:
            st.session_state["agent"].clear()

    st.divider()
    st.markdown("**示例问题**")
    examples = [
        "各大区筹款总额排行",
        "各小组的项目达成率排行",
        "业绩最好的前10名员工",
        "2023年每个月的筹款项目数趋势",
        "各疾病大类的筹款总额占比",
        "三甲和二甲医院的达成率对比",
        "各捐款渠道的捐款金额占比",
        "提现审核通过率是多少？",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["pending_input"] = ex

def _render_feedback(log_id: int):
    state_key = f"fb_state_{log_id}"
    if state_key not in st.session_state:
        st.session_state[state_key] = None  # None / 1 / -1

    col1, col2, col_rest = st.columns([1, 1, 8])
    with col1:
        if st.button("👍", key=f"up_{log_id}"):
            st.session_state[state_key] = 1
    with col2:
        if st.button("👎", key=f"down_{log_id}"):
            st.session_state[state_key] = -1

    if st.session_state[state_key] is not None:
        icon = "👍" if st.session_state[state_key] == 1 else "👎"
        placeholder = "哪里做得好？（可选）" if st.session_state[state_key] == 1 else "哪里有问题？（可选）"
        note = st.text_input(f"{icon} 说说原因", placeholder=placeholder, key=f"note_{log_id}")
        if st.button("提交反馈", key=f"submit_{log_id}"):
            update_feedback(log_id, st.session_state[state_key], note)
            st.session_state[state_key] = None
            st.toast("反馈已提交，谢谢！")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# 展示历史消息
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("df") is not None:
            st.dataframe(msg["df"], use_container_width=True)
        if msg.get("chart") is not None:
            st.plotly_chart(msg["chart"], use_container_width=True)
        if msg.get("insight"):
            with st.expander("💡 智能洞察", expanded=True):
                st.markdown(msg["insight"])
        if msg.get("sql"):
            with st.expander("查看 SQL"):
                st.code(msg["sql"], language="sql")
        # 点赞踩（仅assistant消息且有log_id）
        if msg["role"] == "assistant" and msg.get("log_id"):
            _render_feedback(msg["log_id"])

# 处理输入
user_input = st.chat_input("请输入你的问题，例如：各产品类别的销售额是多少？")
if "pending_input" in st.session_state:
    user_input = st.session_state.pop("pending_input")

if user_input:
    if "agent" not in st.session_state:
        st.error("请先在左侧保存配置")
        st.stop()

    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("查询中..."):
            # 多Agent路由
            ma_result = multi_agent_run(user_input)
            route = ma_result.get("route", "sql")
            route_reason = ma_result.get("reason", "")

            # 如果是sql类型，用完整ChatBIAgent获取图表和洞察
            if route == "sql":
                result = st.session_state["agent"].chat(user_input, enable_insight=enable_insight)
            else:
                result = {
                    "answer": ma_result["answer"],
                    "df": None, "chart": None,
                    "sql": None, "insight": None, "error": None,
                }

        df = result.get("df")
        chart = result.get("chart")
        sql = result.get("sql")
        insight = result.get("insight")
        error = result.get("error")
        answer = result["answer"]

        # 显示路由标签
        route_label = "🔍 数据查询" if route == "sql" else "💬 业务咨询"
        st.caption(f"路由：{route_label}　{route_reason}")

        st.markdown(answer)

        if error:
            st.error(f"错误：{error}")
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)
        elif df is not None and df.empty:
            st.warning("SQL执行成功但返回0条数据")
        if chart is not None:
            st.plotly_chart(chart, use_container_width=True)
        if insight:
            with st.expander("💡 智能洞察", expanded=True):
                st.markdown(insight)
        if sql:
            with st.expander("查看 SQL", expanded=True):
                st.code(sql, language="sql")

        # 写日志
        log_id = log_query(
            question=user_input,
            sql=sql or "",
            answer=answer,
            row_count=len(df) if df is not None else None,
            has_chart=chart is not None,
            error_msg=error,
            insight=insight,
            user_name=st.session_state.get("user_name", "匿名"),
        )

        # 点赞踩
        _render_feedback(log_id)

    st.session_state["messages"].append({
        "role": "assistant",
        "content": answer,
        "df": df,
        "chart": chart,
        "insight": insight,
        "sql": sql,
        "log_id": log_id,
    })
