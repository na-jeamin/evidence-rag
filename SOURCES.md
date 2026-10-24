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
