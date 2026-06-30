import asyncio
import json
import os
import sqlite3

import pandas as pd
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from rag import retrieve_context

load_dotenv()
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DB_PATH = os.path.join(os.path.dirname(__file__), "shuidi.db")

TABLES = ["hospitals", "diseases", "campaigns", "donations", "withdrawals", "regions", "teams", "staff"]

app = Server("chatbi-mcp-server")


# ───────────────────────── 工具列表 ─────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_tables",
            description="列出水滴筹数据库中所有表名，不确定表结构时先调用这个",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_table_schema",
            description="获取指定表的字段名、类型和约束，生成SQL前必须先调用此工具确认列名",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名，必须是数据库中存在的表",
                        "enum": TABLES,
                    }
                },
                "required": ["table_name"],
            },
        ),
        types.Tool(
            name="run_sql_query",
            description=(
                "对水滴筹医疗众筹数据库执行只读SQL查询，返回JSON结果（最多返回50行）。"
                "数据时间范围：2022-01 到 2024-06。"
                "员工业绩关联路径：campaigns.staff_id → staff.staff_id → teams.team_id → regions.region_id。"
                "时间字段格式 YYYY-MM-DD，按月聚合用 strftime('%Y-%m', 字段名)。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "有效的 SQLite SELECT 语句，表名全部小写",
                    }
                },
                "required": ["sql"],
            },
        ),
        types.Tool(
            name="search_knowledge",
            description="从知识库中检索业务背景信息，当需要理解业务含义或指标定义时调用",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要检索的问题或关键词",
                    }
                },
                "required": ["query"],
            },
        ),
    ]


# ───────────────────────── 工具执行 ─────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "list_tables":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        return [types.TextContent(type="text", text=json.dumps(tables, ensure_ascii=False))]

    elif name == "get_table_schema":
        table = arguments["table_name"]
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(f"PRAGMA table_info({table})")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return [types.TextContent(type="text", text=f"表 '{table}' 不存在")]
        schema = [
            {"字段名": r[1], "类型": r[2], "非空": bool(r[3]), "主键": bool(r[5])}
            for r in rows
        ]
        return [types.TextContent(
            type="text",
            text=json.dumps(schema, ensure_ascii=False, indent=2),
        )]

    elif name == "run_sql_query":
        sql = arguments["sql"].strip()
        if not sql.upper().startswith("SELECT"):
            return [types.TextContent(type="text", text="错误：只允许 SELECT 查询，不支持写操作")]
        conn = sqlite3.connect(DB_PATH)
        try:
            df = pd.read_sql_query(sql, conn)
            total = len(df)
            preview = df.head(50)
            records = preview.to_dict(orient="records")
            text = f"共 {total} 行，显示前 {len(preview)} 行：\n"
            text += json.dumps(records, ensure_ascii=False, indent=2, default=str)
            return [types.TextContent(type="text", text=text)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"SQL 执行错误：{e}\nSQL：{sql}")]
        finally:
            conn.close()

    elif name == "search_knowledge":
        query = arguments["query"]
        if not DASHSCOPE_API_KEY:
            return [types.TextContent(type="text", text="未配置 DASHSCOPE_API_KEY，无法检索知识库")]
        context = retrieve_context(query, DASHSCOPE_API_KEY)
        return [types.TextContent(type="text", text=context)]

    return [types.TextContent(type="text", text=f"未知工具：{name}")]


# ───────────────────────── 资源 ─────────────────────────

@app.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="db://shuidi/full-schema",
            name="完整数据库结构",
            description="水滴筹数据库所有表和字段定义",
            mimeType="application/json",
        )
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "db://shuidi/full-schema":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cursor.fetchall()]
        schema = {}
        for t in tables:
            c = conn.execute(f"PRAGMA table_info({t})")
            schema[t] = [{"name": r[1], "type": r[2]} for r in c.fetchall()]
        conn.close()
        return json.dumps(schema, ensure_ascii=False, indent=2)
    raise ValueError(f"未知资源：{uri}")


# ───────────────────────── 启动 ─────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
