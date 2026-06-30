import sqlite3
import pandas as pd
import plotly.express as px
import json
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.tools import tool
from langchain.agents import create_agent
from rag import retrieve_context

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "shuidi.db")

# ─────────────────────── Tools 定义 ───────────────────────

@tool
def run_sql_query(sql: str) -> str:
    """对水滴筹医疗众筹数据库执行 SQLite SQL 查询，返回 JSON 格式结果（最多20行）。
    适用于：筹款金额统计、员工/团队业绩、趋势分析、疾病分布等各类数据查询。
    数据库共8张表：hospitals、diseases、campaigns、donations、withdrawals、regions、teams、staff
    注意：regions/teams/staff 表的名称字段均为 name，多表JOIN时需用别名区分，如 r.name AS region_name
    如果返回错误，请修正SQL后重试，最多重试3次。
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn)
        return df.head(20).to_json(orient="records", force_ascii=False)
    except Exception as e:
        # 返回带修复建议的错误信息，引导 Agent 自动重试
        error_msg = str(e)
        hints = []
        if "no such column" in error_msg:
            hints.append("请先调用 get_table_schema 确认字段名后重试")
        if "no such table" in error_msg:
            hints.append("可用表：hospitals/diseases/campaigns/donations/withdrawals/regions/teams/staff")
        if "ambiguous" in error_msg:
            hints.append("存在同名字段，JOIN时请为表添加别名并使用 alias.column 格式")
        hint_str = "；".join(hints) if hints else "请检查SQL语法后重试"
        return f"SQL执行错误: {error_msg}。{hint_str}。"
    finally:
        conn.close()


@tool
def get_table_schema(table_name: str) -> str:
    """查询数据库中指定表的字段名和类型。
    当不确定表结构时先调用此工具，再生成SQL，避免字段名错误。
    可用表名：hospitals, diseases, campaigns, donations, withdrawals, regions, teams, staff
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        cols = [{"字段名": r[1], "类型": r[2]} for r in cursor.fetchall()]
        return json.dumps(cols, ensure_ascii=False)
    except Exception as e:
        return f"查询失败: {e}"
    finally:
        conn.close()


@tool
def set_chart_config(chart_type: str, x_col: str, y_col: str, title: str) -> str:
    """当查询结果适合可视化时，调用此工具设置图表参数。
    chart_type: bar（数量/金额对比）| line（时间趋势）| pie（占比）| scatter（散点）
    x_col / y_col 必须与 run_sql_query 返回数据中的列名完全一致。
    """
    return json.dumps(
        {"chart_type": chart_type, "x_col": x_col, "y_col": y_col, "title": title},
        ensure_ascii=False
    )


TOOLS = [run_sql_query, get_table_schema, set_chart_config]

SYSTEM_PROMPT = """你是水滴筹数据分析助手，帮助运营人员通过自然语言查询医疗众筹数据库。

工作流程：
1. 如果不确定表结构，先调用 get_table_schema 查看字段
2. 调用 run_sql_query 执行查询（SQLite语法，时间用 strftime('%Y-%m', 字段)）
3. 【必须】查询成功后，判断图表类型并调用 set_chart_config：
   - 分类对比（大区/团队/员工排行）→ chart_type=bar
   - 时间趋势（按月/季度）→ chart_type=line
   - 占比分析（各类别份额）→ chart_type=pie
   - 只有纯文字问题（如"平均值是多少"）才跳过图表
4. 用中文清晰回答用户，说明数据含义和关键发现

数据规则：
- 数据时间范围：2022年1月 到 2024年6月
- regions/teams/staff 的名称字段都是 name，JOIN时用别名区分
- 员工业绩路径：campaigns.staff_id → staff → teams → regions
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

注意：直接给出洞察内容，不要重复数据本身，语言简洁专业像BI分析报告。
"""


# ─────────────────────── 工具函数 ───────────────────────

def make_chart(df: pd.DataFrame, chart_type: str, title: str, x_col: str, y_col: str):
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
    data_str = df.head(20).to_string(index=False)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    stats_lines = []
    for col in numeric_cols:
        s = df[col]
        stats_lines.append(
            f"{col}: 均值={s.mean():.2f}, 最大={s.max():.2f}, 最小={s.min():.2f}, "
            f"标准差={s.std():.2f}, 中位数={s.median():.2f}"
        )
    return data_str, "\n".join(stats_lines) if stats_lines else "无数值列"


# ─────────────────────── ChatBIAgent ───────────────────────

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

        # LangChain 1.x 新 API：create_agent 返回 CompiledStateGraph
        self.agent = create_agent(
            model=self.llm,
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT,
        )

        # 对话历史（LangChain Message 对象列表）
        self.chat_history: list = []

    def clear(self):
        self.chat_history = []

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

    def _parse_steps(self, messages: list) -> tuple[str | None, pd.DataFrame | None, dict | None]:
        """从 agent 返回的 messages 中提取 SQL、DataFrame、图表配置"""
        sql = None
        df = None
        chart_cfg = None

        for msg in messages:
            # ToolMessage 包含工具执行结果
            if hasattr(msg, "name") and hasattr(msg, "content"):
                if msg.name == "run_sql_query":
                    # 尝试从 content 提取 SQL（从对应的 tool_call 找）
                    try:
                        rows = json.loads(msg.content)
                        if isinstance(rows, list):
                            df = pd.DataFrame(rows) if rows else None
                    except Exception:
                        pass

                elif msg.name == "set_chart_config":
                    try:
                        chart_cfg = json.loads(msg.content)
                    except Exception:
                        pass

            # AIMessage 中的 tool_calls 包含调用参数（含SQL）
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("name") == "run_sql_query":
                        sql = tc.get("args", {}).get("sql")

        return sql, df, chart_cfg

    def _run_with_retry(self, input_messages: list, max_retries: int = 3) -> dict:
        """执行 Agent，SQL报错时自动将错误信息追加到消息中重试，最多重试 max_retries 次。"""
        messages = input_messages
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = self.agent.invoke(
                    {"messages": messages},
                    config={"recursion_limit": 15},
                )
                all_messages = result.get("messages", [])

                # 检查最后一次 run_sql_query 是否返回了错误
                sql_error = None
                for msg in reversed(all_messages):
                    if hasattr(msg, "name") and msg.name == "run_sql_query":
                        if "SQL执行错误" in msg.content:
                            sql_error = msg.content
                        break

                if sql_error and attempt < max_retries:
                    # 把错误反馈追加进消息，让 Agent 下一轮修正
                    last_error = sql_error
                    messages = all_messages + [
                        HumanMessage(content=f"上次SQL执行失败：{sql_error}，请修正后重试。")
                    ]
                    continue

                return result

            except Exception as e:
                last_error = str(e)
                if attempt >= max_retries:
                    raise

        raise RuntimeError(f"重试{max_retries}次后仍失败，最后错误：{last_error}")

    def chat(self, user_input: str, enable_insight: bool = True) -> dict:
        context = retrieve_context(user_input, self.api_key)

        # 把 RAG 上下文附加到问题里
        augmented_input = f"{user_input}\n\n[数据库背景知识]\n{context}"

        input_messages = self.chat_history + [HumanMessage(content=augmented_input)]

        try:
            result = self._run_with_retry(input_messages, max_retries=3)
        except Exception as e:
            return {"answer": f"Agent执行出错：{e}", "df": None, "chart": None,
                    "sql": None, "insight": None, "error": str(e)}

        all_messages = result.get("messages", [])

        # 最后一条 AIMessage 是最终回答
        answer = ""
        for msg in reversed(all_messages):
            if isinstance(msg, AIMessage) and msg.content:
                answer = msg.content
                break

        # 解析中间步骤
        sql, df, chart_cfg = self._parse_steps(all_messages)

        # 生成图表
        chart = None
        if chart_cfg and df is not None and not df.empty:
            x_col = chart_cfg.get("x_col", "")
            y_col = chart_cfg.get("y_col", "")
            if x_col in df.columns and y_col in df.columns:
                chart = make_chart(df, chart_cfg["chart_type"], chart_cfg["title"], x_col, y_col)

        # 智能洞察
        insight = None
        if enable_insight and df is not None and not df.empty:
            try:
                insight = self._get_insight(user_input, df)
            except Exception:
                pass

        # 更新对话历史（保留最近3轮=6条消息）
        self.chat_history.append(HumanMessage(content=user_input))
        self.chat_history.append(AIMessage(content=answer))
        if len(self.chat_history) > 6:
            self.chat_history = self.chat_history[-6:]

        return {
            "answer": answer,
            "df": df,
            "chart": chart,
            "sql": sql,
            "insight": insight,
            "error": None,
        }
