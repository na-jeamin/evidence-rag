"""按题卡检查Dense/BM25/Hybrid的标注依据命中与首次命中排名。

--inspect-only仅展示题目；Dense复用本地嵌入缓存，BM25不加载嵌入模型。
--locate-evidence仅在所选资料的全部文本块中定位标注原句。
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


CASES_PATH = Path(__file__).resolve().parent / "evals" / "retrieval_cases.json"


def load_cases(path: Path) -> list[dict]:
    """文件路径→JSON文字→Python字典→题目列表。"""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    cases = data["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("评估文件的cases必须是非空列表。")
    return cases


def has_labeled_evidence(case: dict, retrieved_docs: list) -> bool:
    """检查是否有一个返回块包含标注依据；未命中仍需人工复核。"""
    for doc in retrieved_docs:
        source = Path(doc.metadata["source"]).name
        for option in case["evidence_options"]:
            # 同一块同时满足来源与正文，任一备选依据命中即可。
            if source == option["source"] and option["quote"] in doc.page_content:
                return True

    # 所有块、所有备选都检查完，仍未找到标注依据。
    return False


def first_labeled_evidence_rank(case: dict, retrieved_docs: list) -> int | None:
    """从第1名依次检查，返回首个包含标注依据的排名。"""
    for rank, doc in enumerate(retrieved_docs, start=1):
        # 沿用同一来源和原句匹配规则，排名对应本次返回顺序。
        if has_labeled_evidence(case, [doc]):
            return rank
    return None


def has_all_evidence_groups(case: dict, retrieved_docs: list) -> bool:
    """逐组检查必需信息，任一组缺失就返回False。"""
    groups = case.get("evidence_groups")
    if groups is None:
        # 旧题卡只有备选依据，沿用原来的任一原句匹配。
        return has_labeled_evidence(case, retrieved_docs)
    for group in groups:
        if not has_labeled_evidence(group, retrieved_docs):
            return False
    return bool(groups)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dense/BM25/Hybrid标注依据检查，默认Dense第一题。")
    parser.add_argument("--strategy", choices=["dense", "bm25", "hybrid"], default="dense", help="本次采用的检索方式。")
    parser.add_argument("--cases", type=Path, default=CASES_PATH, help="题卡文件，默认沿用原检索开发题。")
    parser.add_argument("--split", choices=["dev", "holdout"], help="按题卡分组选取可答题。")
    parser.add_argument("--case-id", help="只选当前题卡/分组中的指定题号。")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inspect-only", action="store_true", help="只读取展示题目，不检索。")
    mode.add_argument("--locate-evidence", action="store_true", help="只在全部文本块中定位已标注依据，保存对应编号。")
    parser.add_argument("--corpus", choices=["baseline", "full"], default="baseline", help="baseline为原三篇，full为固定版本21篇。")
    parser.add_argument("--k", type=int, default=3, help="每道题返回块数，须为正整数。")
    parser.add_argument("--all-cases", action="store_true", help="检查文件中的全部题目，默认只检查第一题。")
    parser.add_argument("--candidate-k", type=int, default=3, help="仅Hybrid使用：每路先取几块候选。")
    args = parser.parse_args()
    if args.k <= 0:
        parser.error("--k 必须为正整数。")
    if args.candidate_k <= 0:
        parser.error("--candidate-k 必须为正整数。")

    cases = load_cases(args.cases)
    if args.split:
        cases = [case for case in cases if case.get("split") == args.split]
    if args.case_id:
        cases = [case for case in cases if case["id"] == args.case_id]
    if not cases:
        parser.error("当前选择没有题目，请检查--cases、--split和--case-id。")
    print("加载评估题数：", len(cases))

    for case in cases:
        print(f"\n--- {case['id']} ---")
        print("问题：", case["question"])
        print("参考回答（供人工理解）：", case["reference_answer"])
        print("可接受的原文依据数：", len(case["evidence_options"]))
        for number, option in enumerate(case["evidence_options"], start=1):
            print(f"  依据{number}，来源：{option['source']}")
            print("  原文：", option["quote"])

    if args.inspect_only:
        print("\n当前只读取并展示预先准备的题目和依据，尚未检索或计算命中结果。")
        return

    # 只展示题目时不导入检索依赖；本实验仅复用已经验证过的本地索引构建。
    from inspect_documents import CORPUS_DIRS, load_documents
    from inspect_chunks import CHUNK_SIZE, CHUNK_OVERLAP, prepare_chunks

    selected_cases = cases if args.all_cases else cases[:1]
    if not args.locate_evidence and any(not case["evidence_options"] for case in selected_cases):
        parser.error("检索命中/排名评估需要标注依据，请选择含依据的dev或holdout题组。")
    print(f"\n[1/3] 加载原资料、切分；本次检查{len(selected_cases)}题。", flush=True)
    docs = load_documents(CORPUS_DIRS[args.corpus])
    chunks = prepare_chunks(docs)
    print(f"资料选择：{args.corpus}", flush=True)
    print(f"文档数：{len(docs)}，文本块数：{len(chunks)}", flush=True)

    if args.locate_evidence:
        print("[2/3] 在全部文本块中，按来源和原句逐题定位标注依据。", flush=True)
        located_count = 0
        locations = []
        for case in selected_cases:
            matched_chunks = []
            for chunk in chunks:
                # 复用原来的匹配规则，每次核对一个块，保留所有匹配位置。
                if has_labeled_evidence(case, [chunk]):
                    matched_chunks.append({
                        "chunk_id": chunk.metadata["chunk_id"],
                        "source": Path(chunk.metadata["source"]).name,
                        "page_content": chunk.page_content,
                    })
            located = bool(matched_chunks)
            if located:
                located_count += 1
            print(f"\n{case['id']}：{case['question']}")
            print("标注依据所在编号：", [item["chunk_id"] for item in matched_chunks])
            print("至少一条标注依据可定位：", located)
            locations.append({
                "case_id": case["id"], "question": case["question"],
                "labeled_evidence_located": located, "matched_chunks": matched_chunks,
            })

        now = datetime.now(timezone.utc)
        report = {
            "created_at_utc": now.isoformat(),
            "scope": "核对标注依据在全部文本块中的位置，评估资料准备检查。",
            "configuration": {"corpus": args.corpus, "document_count": len(docs),
                              "chunk_count": len(chunks), "chunk_size": CHUNK_SIZE,
                              "chunk_overlap": CHUNK_OVERLAP},
            "case_count": len(selected_cases), "located_case_count": located_count,
            "cases_snapshot": selected_cases, "results": locations,
            "embedding_called": False, "retrieval_called": False, "generation_called": False,
        }
        output_dir = CASES_PATH.parent / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"evidence_locations_{args.corpus}_{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        print(f"\n标注依据可定位题数：{located_count}/{len(selected_cases)}")
        print("[3/3] 定位报告已保存：", output_path)
        print("当前只核对标注依据位置，尚未测试检索排名或生成回答；未定位的题需复核来源与原句。")
        return

    if args.strategy in ("dense", "hybrid"):
        from retrieve import build_vectorstore

        print("[2/3] 复用缓存嵌入模型，建立内存向量索引。", flush=True)
        vectorstore = build_vectorstore(chunks)
    if args.strategy in ("bm25", "hybrid"):
        from langchain_community.retrievers import BM25Retriever
        from bm25_retrieve import tokenize

        print("[2/3] 复用中文分词规则，建立BM25索引。", flush=True)
        bm25_candidate_k = args.candidate_k if args.strategy == "hybrid" else args.k
        bm25_retriever = BM25Retriever.from_documents(
            chunks, preprocess_func=tokenize, k=bm25_candidate_k,
        )

    if args.strategy == "hybrid":
        from hybrid_retrieve import merge_candidates, calculate_rrf_scores, rank_candidates

        print(f"Hybrid配置：每路候选{args.candidate_k}，最终返回{args.k}，RRF常数60。")

    print("[3/3] 复用同一个索引，逐题检索并核对标注依据。", flush=True)
    hit_count = 0
    results = []
    for case in selected_cases:
        question = case["question"]  # 只传问题，不把标注依据交给检索器。
        route_details = None
        if args.strategy == "dense":
            retrieved_docs = vectorstore.similarity_search(question, k=args.k)
        elif args.strategy == "bm25":
            retrieved_docs = bm25_retriever.invoke(question)
        else:
            # 复用Day10已验证的函数：正文去重，原始两路排名用于累计分数。
            dense_docs = vectorstore.similarity_search(question, k=args.candidate_k)
            bm25_docs = bm25_retriever.invoke(question)
            merged_docs = merge_candidates(dense_docs, bm25_docs)
            rrf_scores = calculate_rrf_scores(dense_docs, bm25_docs)
            ranked_docs = rank_candidates(merged_docs, rrf_scores)
            retrieved_docs = ranked_docs[:args.k]  # 只核对最终选中的块。
            route_details = {
                "dense_ids": [doc.metadata["chunk_id"] for doc in dense_docs],
                "bm25_ids": [doc.metadata["chunk_id"] for doc in bm25_docs],
                "candidate_count_before": len(dense_docs) + len(bm25_docs),
                "unique_count": len(merged_docs),
                "rrf_scores": rrf_scores,
                "all_ranked_ids": [doc.metadata["chunk_id"] for doc in ranked_docs],
            }
        first_rank = first_labeled_evidence_rank(case, retrieved_docs)
        hit = first_rank is not None
        reciprocal_rank = 0.0 if first_rank is None else 1.0 / first_rank
        all_groups_hit = has_all_evidence_groups(case, retrieved_docs)
        if hit:
            hit_count += 1  # 每题最多计1次，不按命中的块数计数。

        print(f"\n{case['id']}：{question}", flush=True)
        if route_details is not None:
            print("向量候选：", route_details["dense_ids"])
            print("BM25候选：", route_details["bm25_ids"])
        print("返回编号：", [doc.metadata["chunk_id"] for doc in retrieved_docs])
        print("标注依据命中：", hit)
        print("首次标注依据排名：", first_rank)
        print("全部必需依据组命中：", all_groups_hit)
        # 完整正文保存进报告，控制台只显示摘要，便于逐题人工复核。
        results.append({
            "case_id": case["id"],
            "question": question,
            "labeled_evidence_hit": hit,
            "first_labeled_evidence_rank": first_rank,
            "reciprocal_rank": reciprocal_rank,
            "all_evidence_groups_hit": all_groups_hit,
            "route_details": route_details,
            "retrieved_docs": [
                {"chunk_id": doc.metadata["chunk_id"],
                 "source": Path(doc.metadata["source"]).name,
                 "page_content": doc.page_content}
                for doc in retrieved_docs
            ],
        })

    print(f"\n标注依据命中题数：{hit_count}/{len(selected_cases)}")
    hit_rate = hit_count / len(selected_cases)
    # 每道未命中的题按0计入分母，保持与命中题使用同一批题目。
    mrr = sum(row["reciprocal_rank"] for row in results) / len(selected_cases)
    print(f"标注依据Hit@{args.k}：{hit_rate:.4f}")
    print(f"标注依据MRR@{args.k}：{mrr:.4f}")
    all_group_hit_count = sum(row["all_evidence_groups_hit"] for row in results)
    all_group_hit_rate = all_group_hit_count / len(selected_cases)
    print(f"全部必需依据组命中题数：{all_group_hit_count}/{len(selected_cases)}")
    print("未命中的题仍需人工复核其他有效依据或标注遗漏。")

    # 保存本次题目/标注与实际返回原文，不覆盖以前的实验报告。
    now = datetime.now(timezone.utc)
    report = {
        "created_at_utc": now.isoformat(),
        "scope": "按预标注来源和原句计算命中、首次排名及必需依据组覆盖，语义支持与答案完整性另行复核。",
        "configuration": {"corpus": args.corpus, "retriever": args.strategy, "k": args.k,
                          "cases_file": str(args.cases.resolve()), "split": args.split,
                          "embedding_model": "BAAI/bge-small-zh-v1.5" if args.strategy in ("dense", "hybrid") else None,
                          "preprocess_func": "tokenize" if args.strategy in ("bm25", "hybrid") else None,
                          "candidate_k_per_route": args.candidate_k if args.strategy == "hybrid" else None,
                          "rank_constant": 60 if args.strategy == "hybrid" else None,
                          "tie_break": "同分保留首次出现顺序，Dense先" if args.strategy == "hybrid" else None,
                          "document_count": len(docs), "chunk_count": len(chunks),
                          "chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP},
        "case_count": len(selected_cases), "hit_count": hit_count,
        "hit_rate_at_k": hit_rate, "mrr_at_k": mrr,
        "all_evidence_groups_hit_rate_at_k": all_group_hit_rate,
        "cases_snapshot": selected_cases, "results": results,
        "generation_called": False,
    }
    output_dir = CASES_PATH.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = f"hybrid_c{args.candidate_k}_k{args.k}" if args.strategy == "hybrid" else f"{args.strategy}_k{args.k}"
    if args.corpus != "baseline":
        tag = f"{args.corpus}_{tag}"
    output_path = output_dir / f"{tag}_{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print("报告已保存：", output_path)
    print(f"本次只检查{args.strategy}一种方式；结果限本题组和配置，未调用生成模型。")


if __name__ == "__main__":
    main()
