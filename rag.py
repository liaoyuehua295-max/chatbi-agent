from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

_vectorstore = None  # reset on each app restart

BASE_KB = os.path.join(os.path.dirname(__file__), "knowledge_base.txt")
CUSTOM_KB = os.path.join(os.path.dirname(__file__), "knowledge_custom.txt")

def _load_text() -> str:
    """合并固定知识库和自定义知识库"""
    texts = []
    for path in [BASE_KB, CUSTOM_KB]:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    texts.append(content)
    return "\n\n".join(texts)

def reset_vectorstore():
    """后台保存知识库后调用，清空缓存"""
    global _vectorstore
    _vectorstore = None

def get_vectorstore(api_key: str):
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    text = _load_text()
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    docs = splitter.create_documents([text])

    embeddings = DashScopeEmbeddings(model="text-embedding-v2", dashscope_api_key=api_key)
    _vectorstore = FAISS.from_documents(docs, embeddings)
    return _vectorstore

def retrieve_context(query: str, api_key: str, k: int = 3) -> str:
    vs = get_vectorstore(api_key)
    docs = vs.similarity_search(query, k=k)
    return "\n".join(d.page_content for d in docs)
