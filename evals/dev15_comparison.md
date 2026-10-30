# 15题检索开发集对照（dev15-v2）

2026-10-30：四组均为用户实际运行，报告题目/标注快照相同，最终均3块。原资料3份、71块，切分500/100；仅开发集，不是独立测试或生成回答准确率。

| 配置 | 标注依据命中题数 | 未命中题 | 报告 |
| --- | --- | --- | --- |
| Dense | 12/15 | Q001、Q012、Q014 | [dense_k3_20261030T084503794456Z.json](results/dense_k3_20261030T084503794456Z.json) |
| BM25 | 15/15 | 无 | [bm25_k3_20261030T085052364880Z.json](results/bm25_k3_20261030T085052364880Z.json) |
| Hybrid每路3 | 13/15 | Q001、Q012 | [hybrid_c3_k3_20261030T085446608757Z.json](results/hybrid_c3_k3_20261030T085446608757Z.json) |
| Hybrid每路6 | 14/15 | Q012 | [hybrid_c6_k3_20261030T085518818124Z.json](results/hybrid_c6_k3_20261030T085518818124Z.json) |

## 逐题结果

| 题号 | Dense | BM25 | Hybrid每路3 | Hybrid每路6 |
| --- | --- | --- | --- | --- |
| Q001 | 未命中 | 命中 | 未命中 | 命中 |
| Q002 | 命中 | 命中 | 命中 | 命中 |
| Q003 | 命中 | 命中 | 命中 | 命中 |
| Q004 | 命中 | 命中 | 命中 | 命中 |
| Q005 | 命中 | 命中 | 命中 | 命中 |
| Q006 | 命中 | 命中 | 命中 | 命中 |
| Q007 | 命中 | 命中 | 命中 | 命中 |
| Q008 | 命中 | 命中 | 命中 | 命中 |
| Q009 | 命中 | 命中 | 命中 | 命中 |
| Q010 | 命中 | 命中 | 命中 | 命中 |
| Q011 | 命中 | 命中 | 命中 | 命中 |
| Q012 | 未命中 | 命中 | 未命中 | 未命中 |
| Q013 | 命中 | 命中 | 命中 | 命中 |
| Q014 | 未命中 | 命中 | 命中 | 命中 |
| Q015 | 命中 | 命中 | 命中 | 命中 |

## 实际失败与解释

- Q001：Hybrid每路3时，C029仅BM25第2名，与Dense第2名C022同分，固定同分顺序排第4；扩大候选后两路共同第6名C027得分2/66，升第1并恢复依据。
- Q012：两个Hybrid配置都已在BM25候选中找到C056，但它只有一路第2名贡献1/62，融合排第5。C023两路都第3名，得分2/63升第1，却主要讲块大小/LLM上下文，不能直接支持“同一个嵌入模型”。因此两路共同命中不保证相关，扩大候选也未解决本例。
- Dense未命中Q001/Q012/Q014；BM25在当前15题全部含标注依据。没有根据该成绩更改默认策略或为各题定制权重。

## 标注修订与限制

Q010原15题v1只标另一段表述，Dense返回C033/C032虽可支持回答却判False；已归档v1及11/15原报告，v2只补等价依据，重跑12/15，15题检索返回全文不变。四组正式对照统一使用v2，不把标注修订称为检索优化。

题目来自同一组已知教程，含技术词，存在选择偏向；BM25的15/15不能视为通用100%准确率。Hybrid每路6比单路k3使用更多候选，不能仅按最终块数相同认为检索预算相同。原文短语匹配可能漏掉未标注的有效解释，仍需人工复核；当前尚未测延迟或生成质量。

## 复现

在D:\tt\agent使用现有环境，分别执行：

```powershell
.\day05-basic-rag\.venv\Scripts\python.exe -X utf8 .\projects\evidence-rag\eval_retrieval.py --all-cases --strategy dense --k 3
.\day05-basic-rag\.venv\Scripts\python.exe -X utf8 .\projects\evidence-rag\eval_retrieval.py --all-cases --strategy bm25 --k 3
.\day05-basic-rag\.venv\Scripts\python.exe -X utf8 .\projects\evidence-rag\eval_retrieval.py --all-cases --strategy hybrid --candidate-k 3 --k 3
.\day05-basic-rag\.venv\Scripts\python.exe -X utf8 .\projects\evidence-rag\eval_retrieval.py --all-cases --strategy hybrid --candidate-k 6 --k 3
```
