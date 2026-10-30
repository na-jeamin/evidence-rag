# 来源、固定版本与本地改动

## 主参考

- 上游：[Datawhale all-in-rag](https://github.com/datawhalechina/all-in-rag)。
- 固定版本：`cec956e80ae28d6c0ca84c9d39dddcf61ad633fd`。
- 基础代码：`code/C1/01_langchain_example.py`，保留于 `reference/01_langchain_example.py`，供对照。
- 上游原 README 保留于 `reference/upstream_README.md`，其中包含作者及许可声明。上游声明 CC BY-NC-SA 4.0，复用原示例、资料及其派生内容保留该署名与许可要求；不声称整套为独立原创或统一改成 MIT。

## 资料

直接使用原仓库的三份教程 Markdown，未改写成自定义业务材料：

1. [数据加载](https://github.com/datawhalechina/all-in-rag/blob/cec956e80ae28d6c0ca84c9d39dddcf61ad633fd/docs/chapter2/04_data_load.md)。
2. [文本切分](https://github.com/datawhalechina/all-in-rag/blob/cec956e80ae28d6c0ca84c9d39dddcf61ad633fd/docs/chapter2/05_text_chunking.md)。
3. [向量嵌入](https://github.com/datawhalechina/all-in-rag/blob/cec956e80ae28d6c0ca84c9d39dddcf61ad633fd/docs/chapter3/06_vector_embedding.md)。

文件路径、上游 Git blob 标识及固定版本链接见 `reference/manifest.json`。这些教程作为问答资料，不代表本项目已实现教程中提到的全部方法；图片和外部服务不在当前加载范围内。

## 当前第一阶段改动

- 沿用 C1 的加载步骤，复用此前本地已跑通的 `TextLoader(encoding="utf-8")` 适配；原 C1 使用 `UnstructuredMarkdownLoader`，两者解析方式不同，不称未经修改的原版运行。
- 从一个路径扩展为目录中三份 Markdown，以 `extend` 汇总每次 `load` 返回的文档列表，保留加载器填写的 `source`。
- 新增无资料时的明确报错、文件数量和正文预览。当前不进行向量计算或模型请求。
- 新建独立项目目录及仓库，避免依赖学习工作区的代码路径；开发时暂复用已有虚拟环境，独立安装依赖的方法见 README。

ATLAS/C7 的反馈图仍为后续候选对照，此阶段未复制或集成其代码。

## 第二阶段：切分观察

`inspect_chunks.py` 复用当前加载函数和 C1 的 RecursiveCharacterTextSplitter，将完整文档列表切成块；保留 source，补当前语料/配置内的 chunk_id，展示来源统计。初始 500/100 是本地实验配置，编号/统计为本地教学改动；不称上游原版，尚未用检索效果证明这些参数最优。

## 第三阶段：Dense 基线（已有用户实际运行）

`retrieve.py` 复用 C1 的 HuggingFaceEmbeddings / InMemoryVectorStore / add_documents / similarity_search 主流程，使用同名 BGE、CPU 和归一化。变化为复用当前多文档/500 字符切分、显式只读本地模型缓存、CLI 问题/Top-K 与编号来源预览；当前尚不生成回答。具体查询、语料和配置与上游原例不同，不称未经修改的原版或已获得优化提升。

## Day 9：BM25 关键词路线（分阶段准备）

- 延续原三份教程与71块，不另换数据来比较。all-in-rag 为检索学习主线，本地BM25入口为适配代码，不称逐字运行C4原版；此前读过的C4 Milvus/BGE-M3稀疏检索示例不等于当前的BM25实现。
- 使用作者发布的 [rank-bm25 0.2.2](https://pypi.org/project/rank-bm25/0.2.2/) 和 [jieba 0.42.1](https://pypi.org/project/jieba/0.42.1/)，2026-10-26 核对 PyPI 版本；用户已实际安装并运行jieba分词观察，2026-10-27进一步验证完整BM25检索及换问法实验。
- rank-bm25 作者示例要求传入词列表，并强调资料和问题使用一致预处理；jieba 官方 README 提供中文分词与 lcut 接口，见 [jieba](https://github.com/fxsjy/jieba)。
- 本地 tokenize 负责切词、英文小写及空白/纯标点清理，保留包含字母/数字/中文的术语；当前未移除停用词，未证明该预处理最优。
- 核对本机 langchain-community 0.4.2 的 retrievers/bm25.py：默认 text.split 不专门处理中文，可通过 preprocess_func 指定同一处理函数，from_documents 保留正文/metadata，invoke接收字符串再处理查询。按此接入索引/查询代码后，先用人工三条文本做隔离接口与无匹配边界检查，再由用户实际运行71块课程语料。两问法结果见evals/bm25_observations.json，不称已获得整体检索提升。

## Day 10：两路合并与RRF分数

复用已有Dense/BM25路线，共用一次加载/切分和块编号。本地merge_candidates负责按编号保留首次出现的完整原文块，calculate_rrf_scores负责等权RRF累计；每路输入为各自不重复的原始排名列表。

2026-10-28核对 [Elastic官方RRF说明](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion)：每路按1/(rank_constant+rank)贡献分，rank从1起，同块多路贡献相加。本地固定常数60作基线，只参考算法原理、自行实现教学代码，不安装或依赖Elasticsearch，不称已复现其服务/API或得到同等效果。评分/排序已写待用户运行；同分保留首次出现顺序、最终--k截取属于本地明确的基线选择，不称与Elastic服务的同分排序一致。

## Day 11：本地标注依据检查

retrieval_cases.json的开发题、参考回答和quote备选由助手对照本项目固定版本的三份原文编写，quote存在性已只读核对，不称官方评测集或独立测试。eval_retrieval.py的来源文件名+原文短语包含检查、逐题计数、报告保存为本地新增逻辑；指标只表示标注依据命中题数，不能直接当作一般检索准确率或生成回答准确率。

Dense分支复用项目已有build_vectorstore，BM25分支复用已核对的BM25Retriever.from_documents/invoke与tokenize，未从新框架搬入评估平台。Hybrid分支直接调用Day10三个融合函数，不修改公式/同分规则。三题四配置均已有用户实际运行和报告核对（Dense2/3、BM253/3、Hybrid候选3为2/3、候选6为3/3，最终均3）；只限开发小集，扩充约15题和独立评估均未完成。
