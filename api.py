"""T1：检索预览与受控问答入口，共用启动时恢复的持久索引。"""

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from openai import APIError, APITimeoutError
from pydantic import BaseModel, ConfigDict, Field


PROJECT_DIR = Path(__file__).resolve().parent
INDEX_PATH = PROJECT_DIR / "artifacts" / "indexes" / "full.json"
MODEL_ENV_FILE = Path(os.environ.get("RAG_ENV_FILE", str(PROJECT_DIR / ".env"))).resolve()


class RetrieveRequest(BaseModel):
    """我们定义的请求格式：问题非空，最多返回10块。"""

    model_config = ConfigDict(strict=True, extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=3, ge=1, le=10)


class AskRequest(BaseModel):
    """问答先只接问题；候选/初始数量固定在服务端，便于沿用已验证配置。"""

    model_config = ConfigDict(
        strict=True, extra="forbid", str_strip_whitespace=True,
        json_schema_extra={"examples": [{"question": "文档加载器除了提取正文，还会抽取哪些信息作为元数据？"}]},
    )
    question: str = Field(min_length=1, max_length=2000)


def load_index(index_path: Path):
    """沿用已有模型配置和保存格式；缺文件时先停止，不加载模型。"""
    if not index_path.is_file():
        raise RuntimeError(f"找不到索引：{index_path}，请先构建或检查路径。")
    from langchain_core.vectorstores import InMemoryVectorStore
    from retrieve import create_embeddings

    store = InMemoryVectorStore.load(str(index_path), embedding=create_embeddings())
    if not store.store:
        raise RuntimeError("索引中没有文本块，请重新构建。")
    return store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 每个服务进程启动时加载一次，后续请求复用原文和文档向量。
    app.state.vectorstore = load_index(INDEX_PATH)
    try:
        app.state.chunks = app.state.vectorstore.get_by_ids(list(app.state.vectorstore.store))
        yield
    finally:
        app.state.vectorstore = None
        app.state.chunks = []


app = FastAPI(title="EvidenceRAG API", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health(request: Request) -> dict:
    return {"status": "ok", "indexed_chunks": len(request.app.state.vectorstore.store)}


@app.post("/retrieve")
def retrieve(payload: RetrieveRequest, request: Request) -> dict:
    """仅检索预览：不调用检查/回答模型，不提供问题答案。"""
    store = request.app.state.vectorstore
    # 把问题交给已恢复的向量库：编码问题、比较已有向量、交回原文块。
    retrieved_docs = store.similarity_search(payload.question, k=payload.k)
    return {
        "question": payload.question,
        "returned": len(retrieved_docs),
        "chunks": [
            {
                "chunk_id": doc.metadata["chunk_id"],
                "source": Path(doc.metadata["source"]).name,
                "text": doc.page_content,
            }
            for doc in retrieved_docs
        ],
    }


@app.post("/ask")
def ask(payload: AskRequest, request: Request) -> dict:
    """复用已有Hybrid→检查→最多补一次→回答/停止；本路由会请求生成模型。"""
    if not MODEL_ENV_FILE.is_file():
        raise HTTPException(status_code=503, detail="未找到模型配置文件，请在服务启动前设置RAG_ENV_FILE。")
    from check_evidence import build_hybrid_candidates, run_checked_rag

    store = request.app.state.vectorstore
    try:
        candidate_docs = build_hybrid_candidates(payload.question, request.app.state.chunks, store, 6)
    except Exception as error:
        raise HTTPException(status_code=500, detail="本地检索失败，请检查索引和服务日志。") from error

    try:
        # 将同一问题和候选交给已经跑过的问答函数；不传参考答案或复核标签。
        result = run_checked_rag(
            payload.question, candidate_docs, 3, MODEL_ENV_FILE,
            check=True, recover=True, generate_answer=True,
        )
    except APITimeoutError as error:
        raise HTTPException(status_code=504, detail="模型请求超时，本次未取得有效结果。") from error
    except APIError as error:
        raise HTTPException(status_code=502, detail="模型服务调用失败，本次未取得有效结果。") from error
    except (ValueError, RuntimeError) as error:
        # 格式错误/摘录或引用不合法是处理失败，不能伪装成资料不足。
        raise HTTPException(status_code=502, detail="模型输出或证据校验未通过，本次结果不可用。") from error

    if result["status"] not in {"answered", "insufficient"}:
        raise HTTPException(status_code=502, detail="问答流程没有产生有效终态。")
    if result["status"] == "answered" and not result["answer"]:
        raise HTTPException(status_code=502, detail="问答流程未返回有效答案。")

    return {
        "question": payload.question,
        "status": result["status"],
        "answer": result["answer"],
        "reason": result["checks"][-1]["result"]["reason"],
        "citation_ids": result["citation_ids"],
        "supplemented": result["supplemented"],
        "check_calls": result["check_calls"],
        "answer_calls": result["answer_calls"],
        "chunks": [
            {"chunk_id": doc["metadata"]["chunk_id"],
             "source": Path(doc["metadata"]["source"]).name,
             "text": doc["page_content"]}
            for doc in result["retrieved_docs"]
        ],
    }
