"""Day 9 第一阶段：观察中文问题的分词，尚未建立 BM25 索引。

后续同一 tokenize 函数将用于文档块与问题，避免两边处理规则不一致。
评分包与中文分词工具来源见 SOURCES.md；不加载模型或读取密钥。
"""

import argparse

import jieba


def tokenize(text: str) -> list[str]:
    """中文切词、英文转小写，去掉空白和纯标点，返回词列表。"""
    raw_terms = jieba.lcut(text)
    terms = []
    for term in raw_terms:
        word = term.strip().lower()
        # 保留含文字或数字的词，保留 chunk_overlap 等混合术语内部的下划线。
        if word and any(char.isalnum() for char in word):
            terms.append(word)
    return terms


def main() -> None:
    parser = argparse.ArgumentParser(description="观察关键词检索前，问题如何拆成词列表。")
    parser.add_argument("--question", default="文本切分为什么要设置重叠？", help="本次观察的问题。")
    args = parser.parse_args()

    question = args.question
    print("原问题：", question)
    print("仅按空格拆分：", question.split())
    query_terms = tokenize(question)
    print("中文分词并清理：", query_terms)
    if not query_terms:
        raise ValueError("问题没有有效词项，请输入文字或数字。")
    print("\n当前只观察问题分词，尚未为文本块建立 BM25 索引或返回检索结果。")


if __name__ == "__main__":
    main()
