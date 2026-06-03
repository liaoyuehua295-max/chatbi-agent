import sqlite3
import pandas as pd
import plotly.express as px
import json
import re
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from rag import retrieve_context

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "shuidi.db")

SYSTEM_PROMPT = """你是水滴筹数据分析助手，帮助运营人员通过自然语言查询水滴筹医疗众筹数据库。

数据库背景知识：
{context}

对话历史：
{history}

你的任务：
1. 理解用户问题
2. 生成正确的SQLite SQL语句查询数据库
3. 根据数据决定是否需要生成图表
4. 用中文清晰回答用户

回复格式必须严格为如下JSON（不要加markdown代码块）：
{{
  "sql": "SELECT ...",
  "answer": "用中文解释查询结果",
  "chart_type": "bar|line|pie|scatter|none",
  "chart_title": "图表标题",
  "x_col": "x轴列名",
  "y_col": "y轴列名"
}}

规则：
- SQL必须是有效的SQLite语法，表名全部小写
- 数据库共8张表：hospitals、diseases、campaigns、donations、withdrawals、regions、teams、staff
- 员工业绩关联路径：campaigns.staff_id → staff.staff_id → teams.team_id → regions.region_id
- 时间字段格式为 YYYY-MM-DD，月份用 strftime('%Y-%m', 时间字段)
- 数据时间范围：2022年1月 到 2024年6月
- 如果不需要图表，chart_type设为none
- 数量/金额比较适合bar图，时间趋势适合line图，占比适合pie图
- x_col和y_col必须和SQL中SELECT的列名完全一致
"""

INSIGHT_PROMPT = """你是一个资深数据分析师，请对以下查询结果进行深度洞察分析。

用户问题：{question}

查询结果数据（前20行）：
{data_summary}

数据统计信息：
{stats}

业务背景知识：
{context}

请从以下角度给出洞察（用中文，分点输出，每点控制在2句以内）：
1. 【异常识别】找出明显偏高或偏低的数值，与基准对比说明异常程度
2. 【原因分析】结合业务背景，推断高/低的可能原因（2-3个）
3. 【对比洞察】横向或纵向对比，指出差距最大的组合
4. 【行动建议】给出1条最值得关注的改进方向

注意：
- 直接给出洞察内容，不要重复数据本身
- 如果数据正常无异常，说明整体表现良好并指出最优项
- 语言简洁专业，像BI分析报告风格
"""

def run_sql(sql: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    return df

def make_chart(df: pd.DataFrame, chart_type: str, title: str, x_col: str, y_col: str):
    # x轴强制转字符串，避免日期/月份被当数值处理导致图表为空
    plot_df = df.copy()
    if x_col in plot_df.columns:
        plot_df[x_col] = plot_df[x_col].astype(str)
    if chart_type == "bar":
        return px.bar(plot_df, x=x_col, y=y_col, title=title)
    elif chart_type == "line":
        return px.line(plot_df, x=x_col, y=y_col, title=title, markers=True)
    elif chart_type == "pie":
        return px.pie(plot_df, names=x_col, values=y_col, title=title)
    elif chart_type == "scatter":
        return px.scatter(plot_df, x=x_col, y=y_col, title=title)
    return None

def _build_data_summary(df: pd.DataFrame) -> tuple[str, str]:
    """把DataFrame转成文本摘要，避免token过多"""
    data_str = df.head(20).to_string(index=False)

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    stats_lines = []
    for col in numeric_cols:
        s = df[col]
        stats_lines.append(
            f"{col}: 均值={s.mean():.2f}, 最大={s.max():.2f}, 最小={s.min():.2f}, "
            f"标准差={s.std():.2f}, 中位数={s.median():.2f}"
        )
    stats_str = "\n".join(stats_lines) if stats_lines else "无数值列"
    return data_str, stats_str


class ChatBIAgent:
    def __init__(self, api_key: str, base_url: str, model: str, langsmith_key: str = None):
        self.api_key = api_key
        if langsmith_key:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = langsmith_key

        self.llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.3,
        )
        self.history: list = []

    def _format_history(self) -> str:
        if not self.history:
            return "无"
        lines = []
        for human, ai in self.history[-3:]:
            lines.append(f"用户: {human}")
            lines.append(f"助手: {ai}")
        return "\n".join(lines)

    def clear(self):
        self.history = []

    def _get_insight(self, question: str, df: pd.DataFrame) -> str:
        data_summary, stats = _build_data_summary(df)
        context = retrieve_context(question, self.api_key)
        prompt = INSIGHT_PROMPT.format(
            question=question,
            data_summary=data_summary,
            stats=stats,
            context=context,
        )
        response = self.llm.invoke([SystemMessage(content=prompt)])
        return response.content.strip()

    def chat(self, user_input: str, enable_insight: bool = True):
        context = retrieve_context(user_input, self.api_key)
        history = self._format_history()

        prompt = SYSTEM_PROMPT.format(context=context, history=history)
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=user_input),
        ]

        response = self.llm.invoke(messages)
        raw = response.content.strip()

        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            self.history.append((user_input, raw))
            return {"answer": raw, "df": None, "chart": None, "sql": None, "insight": None}

        sql = result.get("sql", "")
        answer = result.get("answer", "")
        chart_type = result.get("chart_type", "none")
        chart_title = result.get("chart_title", "")
        x_col = result.get("x_col", "")
        y_col = result.get("y_col", "")

        df = None
        chart = None
        insight = None
        error = None

        if sql:
            try:
                df = run_sql(sql)
                if chart_type != "none" and x_col and y_col and x_col in df.columns and y_col in df.columns:
                    chart = make_chart(df, chart_type, chart_title, x_col, y_col)
                if enable_insight and df is not None and not df.empty:
                    insight = self._get_insight(user_input, df)
            except Exception as e:
                error = str(e)
                answer = f"SQL执行出错：{e}\n\nSQL：{sql}"

        self.history.append((user_input, answer))

        return {"answer": answer, "df": df, "chart": chart, "sql": sql, "insight": insight, "error": error}
