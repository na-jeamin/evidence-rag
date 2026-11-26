# EvidenceRAG：带依据检查与有限补充的多文档问答

在多篇技术文档中检索依据，先由模型摘录原句并经程序核对充分性、不足时最多补充一次候选原文，再生成带原文块引用的回答或明确停止。

## 它做了什么 / 不做什么

**做了什么：**

- 固定 21 篇参考教程快照（498 个文本块，`chunk_size=500`、`chunk_overlap=100`），索引构建与在线问答分离，索引持久化至 `artifacts/indexes/full.json`。
- 在同一批带编号文本块上对比 Dense（`BAAI/bge-small-zh-v1.5` CPU 本地缓存）、中文 BM25（`jieba` + `rank-bm25`）与等权 RRF 混合检索（`rank_constant=60`，每路取 6 块融合）。
- 在生成回答前增加结构化证据检查（Pydantic 校验 `sufficient / reason / evidence`）与逐字原句存在性核对；首次判不足且存在保留候选时最多补充一次复查，仍不足则停止并返回 `insufficient`（`answer=null`）。
- 回答生成后执行 `[C数字]` 引用编号核对，通过 FastAPI 提供 `/health`、`/retrieve`、`/ask` 接口，并附带检索与问答评估脚本及人工复核记录工具。

**不做什么：**

- 不自动改写问题（Query Rewrite）、不做多轮循环重检、不引入重排模型（Reranker）或跨会话记忆。
- 不依赖云端向量数据库，当前全量索引保存为本地 JSON，运行时加载到内存 `InMemoryVectorStore`（BM25 索引在请求或评估时从已恢复文本块构建）。
- 不承诺新机器从零安装已实测通过（新环境完整复现**未验证**），也不将开发集状态符合率等同于答案语义准确率。

## 架构与数据流

```text
[21 篇 Markdown] ──> inspect_documents / inspect_chunks ──> build_index.py ──> artifacts/indexes/full.json
                                                                                      │
用户问题 ──> FastAPI (/retrieve, /ask) 或 check_evidence.py <─────────────────────────┘
                │
                ├── Dense (BGE) ──┐
                └── BM25 (jieba) ─┴─> RRF 融合 (每路 6 候选 -> 保留池 6 块 -> 初始取前 3 块)
                                        │
                                        ▼
                        证据检查 (JSON + Pydantic + 逐字原句核对)
                          ├── sufficient=True ──> 生成回答 + [C数字] 编号核对 ──> answered
                          └── sufficient=False & 允许补充 ──> 扩至 6 块复查一次
                                ├── sufficient=True ──> 生成回答 ──> answered
                                └── 仍为 False ──────> 停止回答 ──> insufficient (answer=null)
```

| 模块 | 职责 |
| --- | --- |
| [inspect_documents.py](inspect_documents.py) | 加载 `baseline`（3 篇）或 `full`（21 篇）Markdown 文档并保留 `source` 元数据 |
| [inspect_chunks.py](inspect_chunks.py) | 按 500/100 切分文档、生成连续 `C001` 编号并支持按原句定位块 |
| [retrieve.py](retrieve.py) | 配置本地 CPU 版 BGE 嵌入模型与 `InMemoryVectorStore` Dense 检索基线 |
| [bm25_retrieve.py](bm25_retrieve.py) | 定义 `jieba` 中文分词与小写清理规则 `tokenize`，提供 BM25 检索入口 |
| [hybrid_retrieve.py](hybrid_retrieve.py) | 按 `chunk_id` 去重合并两路候选并计算等权 RRF 分数排序 |
| [build_index.py](build_index.py) / [query_index.py](query_index.py) | 将向量、正文和元数据原子写入本地 JSON 索引，或加载已有索引执行 Dense 查询 |
| [check_evidence.py](check_evidence.py) | 编排 Hybrid 候选、结构化检查、逐字原句校验、最多一次候选补充与带引用回答 |
| [api.py](api.py) | FastAPI 服务入口，启动时加载持久索引并暴露 `/health`、`/retrieve`、`/ask`（映射 422/500/502/503/504） |
| [eval_retrieval.py](eval_retrieval.py) | 在题卡上对比 Dense/BM25/Hybrid 的 Hit@3、MRR@3、必需依据组命中及原文位置核对 |
| [eval_rag.py](eval_rag.py) | 批量运行受控问答流程，逐题记录状态符合性、调用次数、耗时与 Token 用量 |
| [review_rag.py](review_rag.py) / [summarize_reviews.py](summarize_reviews.py) | 离线展示问答答卷并保存人工复核结论至 `evals/reviews/`，按原报告 SHA-256 汇总 |

## 快速开始

> 说明：本仓库**不包含 `.venv`**。推荐使用 [scripts/bootstrap.ps1](scripts/bootstrap.ps1) 初始化；该脚本及新机器从零完整安装**未验证**，以下手动命令按本机已验证环境（Python 3.13.5、`torch==2.14.1+cpu`）整理。

### 方式一：引导脚本（未实际执行验证）

```powershell
# 在仓库根目录执行，可通过 -SkipPythonCheck / -SkipVenv / -SkipInstall / -SkipEnvNotice 跳过对应步骤
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
```

### 方式二：手动初始化

1. **创建虚拟环境并安装 CPU 版依赖**（在仓库根目录执行，[requirements-all.txt](requirements-all.txt) 汇总了全部运行与接口依赖）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-all.txt
```

2. **配置环境变量并准备本地索引**：

```powershell
Copy-Item .env.example .env
# 在 .env 中填写本机 LLM_API_KEY、LLM_BASE_URL（默认 https://api.deepseek.com）、LLM_MODEL_ID
.\.venv\Scripts\python.exe -X utf8 .\build_index.py --corpus full
```

3. **命令行问答与 HTTP 接口**：

```powershell
# 单题受控问答（Hybrid 每路 6 候选、初始 3 块、开启一次补充）
.\.venv\Scripts\python.exe -X utf8 .\check_evidence.py --index .\artifacts\indexes\full.json --strategy hybrid --candidate-k 6 --k 3 --check --recover --answer --question "文档加载器除了提取正文，还会抽取哪些信息作为元数据？"

# 启动 HTTP 服务，访问 http://127.0.0.1:8001/docs，请求样例见 requests/ 目录
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8001
```

4. **运行离线测试与检索/问答评估**：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 .\eval_retrieval.py --cases .\evals\rag_cases_full.json --split holdout --corpus full --strategy hybrid --candidate-k 6 --k 3 --all-cases
.\.venv\Scripts\python.exe -X utf8 .\eval_rag.py --cases .\evals\rag_generation_cases.json --split holdout --strategy hybrid --candidate-k 6 --k 3 --run --recover
```

## 评估结果

**检索对照 · 开发 20 题**（[evals/dev20_full_comparison.md](evals/dev20_full_comparison.md)，21 篇资料 / 498 块 / chunk 500-100 / 最终 K=3）：

| 方法 | 任一标注原句命中 | Hit@3 | MRR@3 | 全部必需依据组命中 |
| --- | --- | --- | --- | --- |
| Dense | 15/20 | 0.7500 | 0.6167 | 15/20 |
| BM25 | 19/20 | 0.9500 | 0.9167 | 18/20 |
| Hybrid（每路 6 / 最终 3） | 19/20 | 0.9500 | 0.7250 | 18/20 |

**检索对照 · 留出 10 题**（[evals/holdout10_full_comparison.md](evals/holdout10_full_comparison.md)，初始冻结 v2 口径）：

| 方法 | Hit@3 | MRR@3 | 全部依据组命中 |
| --- | --- | --- | --- |
| BM25（原始运行） | 0.9000 | 0.9000 | 8/10 |
| Dense（相同返回块离线评分） | 0.8000 | 0.5667 | 8/10 |
| Hybrid（相同返回块离线评分） | 0.9000 | 0.7000 | 9/10 |

**问答对照 · 固定 15 题**（[evals/generation_subset_comparison.md](evals/generation_subset_comparison.md)，Hybrid 6/3）：

| 题组 | 预期状态符合 | 实际状态 | 检查/回答尝试 | 总 Token | 逐题耗时合计 |
| --- | --- | --- | --- | --- | --- |
| 可答 10 题，关闭补充 | 9/10 | 回答 9、资料不足 1 | 10/9 | 19488 | 40.85 秒 |
| 不足 5 题，关闭补充 | 5/5 | 资料不足 5 | 5/0 | 5005 | 11.19 秒 |
| 可答 10 题，开启一次补充 | 9/10 | 回答 9、资料不足 1 | 12/9 | 24158 | 43.59 秒 |
| 不足 5 题，开启一次补充 | 5/5 | 资料不足 5 | 10/0 | 12948 | 18.77 秒 |

## 已知限制与来源

**已知限制：**

- Hybrid 的 Hit@3 与 BM25 持平，但 MRR@3 低 0.19：融合把本应排第一的依据压到了第 6 位（开发题 Q012 的 C002）。
- “开启一次候选补充”在本数据集上净收益接近零：H010 被救回（+3732 Token），H001 反而被误判为资料不足（多消耗 980 Token，由 2184 增至 3164），状态符合率仍是 9/10。
- 生成质量目前只有“状态符合率”，答案语义只人工复核了 4/34 份，其余待复核。

**参考来源与改动范围：**

- 上游语料与起步示例参考 [datawhalechina/all-in-rag](https://github.com/datawhalechina/all-in-rag)（固定提交 `cec956e80ae28d6c0ca84c9d39dddcf61ad633fd`，CC BY-NC-SA 4.0），逐文件对照与许可声明见 [SOURCES.md](SOURCES.md)。
- 本项目在参考示例的文档加载、切分与 Dense 检索基础上，自行适配/新增了多文档编号切分、中文 BM25 预处理、RRF 混合融合、JSON 索引持久化、结构化证据检查与一次候选补充、FastAPI 接口以及检索/问答评估与复核脚本。
- 按日期倒序的原始开发与实验过程记录保留在 [docs/HISTORY.md](docs/HISTORY.md)。
