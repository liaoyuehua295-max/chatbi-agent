# 医疗众筹 ChatBI Agent

基于 LangChain + RAG + Text-to-SQL 的医疗众筹数据分析助手。

## 功能特性

- 自然语言查询数据库，自动生成 SQL
- RAG 知识库（固定知识库 + 自定义知识库）
- 智能洞察分析：异常识别、归因分析、行动建议
- 多轮对话记忆
- 用户反馈（点赞/踩）+ 查询日志
- 运营后台：日志查看、数据集预览、数据清洗、知识库编辑

## 技术栈

- LangChain + 通义千问（Qwen）
- FAISS 向量检索
- SQLite 数据库
- Streamlit 前端
- LangSmith 链路追踪

## 快速开始

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置环境变量，新建 `.env` 文件：
```
DASHSCOPE_API_KEY=你的通义千问APIKey
LANGCHAIN_API_KEY=你的LangSmithAPIKey（可选）
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ChatBI-Agent
```

3. 生成模拟数据
```bash
python gen_data.py
python gen_staff.py
```

4. 启动应用
```bash
streamlit run app.py
```

5. 后台地址：`http://localhost:8501/admin`，默认密码：`chatbi2024`

## 项目结构

```
chatbi-agent/
├── app.py              # 前端主页面
├── agent.py            # ChatBI Agent核心
├── rag.py              # RAG知识库检索
├── logger.py           # 查询日志记录
├── gen_data.py         # 医疗众筹模拟数据生成
├── gen_staff.py        # 团队员工数据生成
├── knowledge_base.txt  # 固定知识库
├── knowledge_custom.txt# 自定义知识库
├── pages/
│   └── admin.py        # 运营后台
└── requirements.txt
```
