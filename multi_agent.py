"""
多智能体系统：基于 LangGraph 的路由 + 专业 Agent 架构
结构：
    START → 路由Agent → [查询Agent | 咨询Agent] → END
"""

import os
from typing import TypedDict, Literal
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from rag import retrieve_context

load_dotenv()

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"


def _get_llm():
    return ChatOpenAI(model=MODEL, api_key=API_KEY, base_url=BASE_URL, temperature=0.3)


# ─────────────────────── 1. 共享状态 ───────────────────────

class AgentState(TypedDict):
    user_input: str       # 原始问题
    route: str            # 路由结果: "sql" | "consult"
    route_reason: str     # 路由理由（便于调试）
    sql: str              # 执行的SQL（查询Agent填写）
    data_summary: str     # 查询结果摘要
    final_answer: str     # 最终回答


# ─────────────────────── 2. 路由Agent ───────────────────────

def router_node(state: AgentState) -> AgentState:
    """判断问题类型，决定分发给哪个专业Agent"""
    llm = _get_llm()
    response = llm.invoke([
        SystemMessage(content="""你是一个问题分类器。判断用户问题属于哪种类型，严格按格式回复：

类型1 - sql：需要查询数据库，涉及金额、人数、排行、趋势、统计、对比等
类型2 - consult：业务咨询，涉及规则、流程、政策、解释、建议等

只回复如下JSON格式，不要加任何其他内容：
{"route": "sql", "reason": "问题涉及数据查询"}
或
{"route": "consult", "reason": "问题涉及业务咨询"}"""),
        HumanMessage(content=state["user_input"])
    ])

    import json, re
    raw = response.content.strip()
    raw = re.sub(r"```.*?```", "", raw, flags=re.DOTALL).strip()
    try:
        result = json.loads(raw)
        route = result.get("route", "sql")
        reason = result.get("reason", "")
    except Exception:
        route = "sql"
        reason = "解析失败，默认路由到sql"

    print(f"[路由Agent] → {route}（{reason}）")
    return {**state, "route": route, "route_reason": reason}


# ─────────────────────── 3. 查询Agent ───────────────────────

def sql_agent_node(state: AgentState) -> AgentState:
    """专门处理数据查询类问题，调用 ChatBIAgent"""
    from agent import ChatBIAgent
    agent = ChatBIAgent(API_KEY, BASE_URL, MODEL)
    result = agent.chat(state["user_input"], enable_insight=False)

    answer = result.get("answer", "查询失败")
    sql = result.get("sql", "")
    df = result.get("df")
    data_summary = df.head(5).to_string(index=False) if df is not None and not df.empty else "无数据"

    print(f"[查询Agent] SQL: {sql[:80]}...")
    return {**state, "final_answer": answer, "sql": sql, "data_summary": data_summary}


# ─────────────────────── 4. 咨询Agent ───────────────────────

def consult_agent_node(state: AgentState) -> AgentState:
    """专门处理业务咨询类问题，基于RAG知识库回答"""
    llm = _get_llm()
    context = retrieve_context(state["user_input"], API_KEY)

    response = llm.invoke([
        SystemMessage(content=f"""你是水滴筹业务顾问，基于以下知识库内容回答用户问题。
如果知识库没有相关信息，说明暂无相关资料并给出合理建议。

知识库内容：
{context}"""),
        HumanMessage(content=state["user_input"])
    ])

    print(f"[咨询Agent] 基于RAG知识库回答")
    return {**state, "final_answer": response.content, "sql": "", "data_summary": ""}


# ─────────────────────── 5. 条件边函数 ───────────────────────

def route_condition(state: AgentState) -> Literal["sql_agent", "consult_agent"]:
    if state.get("route") == "sql":
        return "sql_agent"
    return "consult_agent"


# ─────────────────────── 6. 构建图 ───────────────────────

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router",        router_node)
    graph.add_node("sql_agent",     sql_agent_node)
    graph.add_node("consult_agent", consult_agent_node)

    # 入口 → 路由
    graph.add_edge(START, "router")

    # 路由 → 条件分支
    graph.add_conditional_edges(
        "router",
        route_condition,
        {
            "sql_agent":     "sql_agent",
            "consult_agent": "consult_agent",
        }
    )

    # 两个Agent都直接结束
    graph.add_edge("sql_agent",     END)
    graph.add_edge("consult_agent", END)

    return graph.compile()


# ─────────────────────── 7. 对外接口 ───────────────────────

# 全局编译一次
_app = None

def get_app():
    global _app
    if _app is None:
        _app = build_graph()
    return _app


def run(user_input: str) -> dict:
    """
    运行多智能体系统，返回结构化结果。
    返回: {answer, route, reason, sql, data_summary}
    """
    app = get_app()
    initial_state: AgentState = {
        "user_input": user_input,
        "route": "",
        "route_reason": "",
        "sql": "",
        "data_summary": "",
        "final_answer": "",
    }
    result = app.invoke(initial_state)
    return {
        "answer":       result["final_answer"],
        "route":        result["route"],
        "reason":       result["route_reason"],
        "sql":          result["sql"],
        "data_summary": result["data_summary"],
    }


# ─────────────────────── 8. 本地测试 ───────────────────────

if __name__ == "__main__":
    test_questions = [
        "各大区筹款总额排行",           # 应路由到 sql_agent
        "水滴筹的提现审核流程是怎样的",  # 应路由到 consult_agent
        "2023年每月筹款项目数趋势",      # 应路由到 sql_agent
    ]

    for q in test_questions:
        print("\n" + "="*60)
        print(f"问题：{q}")
        result = run(q)
        print(f"路由：{result['route']}（{result['reason']}）")
        print(f"回答：{result['answer'][:150]}...")
        if result["sql"]:
            print(f"SQL：{result['sql'][:100]}...")
