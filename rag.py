"""
RAG 知识库检索模块
向量数据库：Qdrant 本地持久化版（替代原FAISS内存版）
关键设计：全局单例 client + vectorstore，整个进程只开一次文件锁
"""
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
import os

COLLECTION_NAME = "chatbi_knowledge"
QDRANT_PATH     = os.path.join(os.path.dirname(__file__), "qdrant_local")

BASE_KB   = os.path.join(os.path.dirname(__file__), "knowledge_base.txt")
CUSTOM_KB = os.path.join(os.path.dirname(__file__), "knowledge_custom.txt")

# 全局单例
_client:      QdrantClient      | None = None
_vectorstore: QdrantVectorStore | None = None


def _load_text() -> str:
    texts = []
    for path in [BASE_KB, CUSTOM_KB]:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    texts.append(content)
    return "\n\n".join(texts)


def _get_embeddings(api_key: str) -> DashScopeEmbeddings:
    return DashScopeEmbeddings(
        model="text-embedding-v2",
        dashscope_api_key=api_key
    )


def _collection_exists() -> bool:
    """通过文件系统判断集合是否已存在，避免重复开 client"""
    return os.path.exists(os.path.join(QDRANT_PATH, "collection", COLLECTION_NAME))


def get_vectorstore(api_key: str) -> QdrantVectorStore:
    global _client, _vectorstore

    # 已初始化直接返回，整个进程只走一次初始化
    if _vectorstore is not None:
        return _vectorstore

    embeddings = _get_embeddings(api_key)

    if not _collection_exists():
        # ── 首次构建：from_documents 内部创建 client ──
        print("[Qdrant] 首次构建向量索引，正在 Embedding 知识库...")
        text = _load_text()
        splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
        docs = splitter.create_documents([text])

        _vectorstore = QdrantVectorStore.from_documents(
            docs,
            embeddings,
            path=QDRANT_PATH,
            collection_name=COLLECTION_NAME,
        )
        _client = _vectorstore.client  # 复用内部 client，不再重新打开
        print(f"[Qdrant] 完成，共 {len(docs)} 个 chunk，持久化至 {QDRANT_PATH}")

    else:
        # ── 已存在：用单例 client 直接加载 ──
        print("[Qdrant] 加载已有索引（跳过 Embedding）")
        _client = QdrantClient(path=QDRANT_PATH)
        _vectorstore = QdrantVectorStore(
            client=_client,
            collection_name=COLLECTION_NAME,
            embedding=embeddings,
        )

    return _vectorstore


def reset_vectorstore():
    """知识库更新后调用，清除旧索引，下次查询时重建"""
    global _client, _vectorstore
    _vectorstore = None

    if _client is not None:
        _client.delete_collection(COLLECTION_NAME)
        _client.close()
        _client = None
        print("[Qdrant] 旧索引已清除，下次查询时重建")
    elif os.path.exists(QDRANT_PATH):
        # client 未初始化但文件存在，直接删目录
        import shutil
        shutil.rmtree(QDRANT_PATH)
        print("[Qdrant] 旧索引目录已删除")


def retrieve_context(query: str, api_key: str, k: int = 3) -> str:
    vs = get_vectorstore(api_key)
    docs = vs.similarity_search(query, k=k)
    return "\n".join(d.page_content for d in docs)
