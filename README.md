# EvidenceRAG：带依据门控与有界补充的多文档问答系统

面向固定技术文档语料的检索增强生成（RAG）服务。系统将离线索引与在线问答解耦，通过 **稠密向量 + 中文 BM25 双路召回与 RRF 融合** 获取候选片段，并在生成答案前引入 **结构化证据门控、逐字原句核对与最多一次候选扩窗补充**，在证据充分时输出带 `[C数字]` 引用的回答，在资料缺失时受控停止并返回空答案，避免模型靠参数记忆编造内容。

## 核心能力与明确边界

**已实现能力：**

- **离线索引与在线服务解耦**：基于固定 21 篇中文教程快照（按 `chunk_size=500`、`chunk_overlap=100` 切出 498 个连续编号文本块），通过临时文件原子替换持久化索引至 `artifacts/indexes/full.json`，FastAPI 进程启动时一次性加载复用。
- **双路召回与倒数秩融合**：在同一批文本块上实现并对比了 Dense（本地 CPU 版 `BAAI/bge-small-zh-v1.5`）、中文分词 BM25（`jieba` + `rank-bm25`）与等权 RRF 混合检索（`rank_constant=60`，每路取 6 块去重融合）。
- **生成前证据门控与有界扩窗**：生成前强制模型输出严格 JSON（由 Pydantic 校验 `sufficient / reason / evidence`）并在本地逐字核对原句存在于对应块正文；首次判不足时最多将上下文从初选 3 块扩至保留池 6 块复查一次，仍不足则终止并返回 `status="insufficient"`（`answer=null`）。
- **引用校验、接口封装与多维评测**：回答生成后校验 `[C数字]` 引用编号范围；对外暴露 `/health`、`/retrieve`、`/ask` 接口（按 422/500/502/503/504 区分错误边界）；配套 35 题分组检索评估、15 题问答成本对照、人工复核工具及 18 项无网络离线单元测试。

**范围边界（不做什么）：**

- 不做自动 Query 改写、不开放多轮循环重检、未接入重排模型（Reranker）与跨会话记忆；
- 不依赖外部向量数据库服务，当前采用本地 JSON 持久化 + 内存向量库（BM25 索引在启动或评估时从已恢复文本块构建）；
- 不把“状态符合率”混称为“答案语义准确率”，也不宣称新机器冷启动安装脚本已经过零缓存环境实测。

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
| [retrieve.py](retrieve.py) | 统一定义本地 CPU 版 BGE 嵌入模型配置与 `InMemoryVectorStore` Dense 检索基线 |
| [bm25_retrieve.py](bm25_retrieve.py) | 实现 `jieba` 中文分词与符号过滤规则 `tokenize`，提供中文 BM25 检索入口 |
| [hybrid_retrieve.py](hybrid_retrieve.py) | 按 `chunk_id` 去重合并两路候选并计算等权 RRF 分数排序 |
| [build_index.py](build_index.py) / [query_index.py](query_index.py) | 将向量、正文和元数据原子写入本地 JSON 索引，或加载已有索引执行 Dense 查询 |
| [check_evidence.py](check_evidence.py) | 编排 Hybrid 候选、结构化证据检查、逐字核对、单次有界扩窗与带引用回答 |
| [api.py](api.py) | FastAPI 服务入口，Lifespan 加载持久索引并暴露 `/health`、`/retrieve`、`/ask` |
| [eval_retrieval.py](eval_retrieval.py) | 在题卡上对比 Dense/BM25/Hybrid 的 Hit@3、MRR@3、必需依据组全覆盖及原句定位 |
| [eval_rag.py](eval_rag.py) | 批量运行受控问答流程，记录预期状态符合率、调用次数、耗时与 Token 用量 |
| [review_rag.py](review_rag.py) / [summarize_reviews.py](summarize_reviews.py) | 离线展示问答答卷并记录人工语义复核结论至 `evals/reviews/`，按原报告 SHA-256 汇总 |

## 快速开始

> 环境说明：本仓库不包含 `.venv`。以下手动步骤按本机已验证环境（Python 3.13.5、`torch==2.14.1+cpu`）整理；仓库同时提供一键引导脚本 [scripts/bootstrap.ps1](scripts/bootstrap.ps1)（已通过语法检查，新机器零缓存实测待验证）。

### 1. 初始化虚拟环境与依赖

```powershell
# 方式一（可选引导脚本，新机冷启动未实测）
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1

# 方式二（手动安装，在仓库根目录执行，requirements-all.txt 汇总全部运行与接口依赖）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-all.txt
```

### 2. 配置模型变量并构建本地索引

```powershell
Copy-Item .env.example .env
# 在 .env 中填写 LLM_API_KEY、LLM_BASE_URL（默认 https://api.deepseek.com）、LLM_MODEL_ID
.\.venv\Scripts\python.exe -X utf8 .\build_index.py --corpus full
```

### 3. 运行命令行问答或启动 HTTP 接口

```powershell
# 单题受控问答（Hybrid 每路 6 候选、初选 3 块、开启单次 3->6 补充）
.\.venv\Scripts\python.exe -X utf8 .\check_evidence.py --index .\artifacts\indexes\full.json --strategy hybrid --candidate-k 6 --k 3 --check --recover --answer --question "文档加载器除了提取正文，还会抽取哪些信息作为元数据？"

# 启动 FastAPI 服务，浏览器打开 http://127.0.0.1:8001/docs（请求示例见 requests/ 目录）
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8001
```

### 4. 运行离线单元测试与评估脚本

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 .\eval_retrieval.py --cases .\evals\rag_cases_full.json --split holdout --corpus full --strategy hybrid --candidate-k 6 --k 3 --all-cases
.\.venv\Scripts\python.exe -X utf8 .\eval_rag.py --cases .\evals\rag_generation_cases.json --split holdout --strategy hybrid --candidate-k 6 --k 3 --run --recover
```

## 评估结果

**检索对照 · 开发 20 题**（[evals/dev20_full_comparison.md](evals/dev20_full_comparison.md)，21 篇 / 498 块 / 500-100 切分 / K=3）：

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

## 已知局限与后续改进方向

- **RRF 融合导致排序靠后**：开发集上 Hybrid 与 BM25 的 `Hit@3` 持平（`0.95`），但 `MRR@3` 低 `0.1917`（如 `Q012` 的直接依据 `C002` 在融合后被两路共现的背景块压至第 6 位）。后续计划在 RRF 候选池后引入轻量 Cross-Encoder Rerank 模型精排并同题对比延迟与 MRR 收益。
- **单次候选补充的净收益与成本权衡**：固定 15 题对照中，开启 3→6 扩窗救回了依据排在第 4 位的 `H010`（+3732 Token），但 `H001` 受检查模型波动影响出现误拒（多消耗 980 Token，由 2184 增至 3164），且 5 道无答案题均多执行一次 6 块复查，整体状态符合率仍为 `14/15`、总 Token 由 `24493` 升至 `37106`。
- **答案语义人工复核尚未全量完成**：目前已完成 `4/34` 份已答样本的人工逐句核对，其余样本待继续补齐复核记录。

## 参考来源与演进记录

- 上游语料与起步示例参考 [datawhalechina/all-in-rag](https://github.com/datawhalechina/all-in-rag)（固定提交 `cec956e80ae28d6c0ca84c9d39dddcf61ad633fd`，CC BY-NC-SA 4.0），逐文件对照与许可说明见 [SOURCES.md](SOURCES.md)。
- 本项目在参考示例的文档加载、切分与 Dense 检索基础上，自行适配/新增了多文档编号切分、中文 BM25 预处理、RRF 混合融合、JSON 索引持久化、结构化证据检查与单次候选补充、FastAPI 接口以及检索/问答评估与复核脚本。
- 按日期倒序的原始开发与实验日志保留在 [docs/HISTORY.md](docs/HISTORY.md)。
