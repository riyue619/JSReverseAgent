"""
工具11:vector_search(向量检索)
用于在向量数据库中检索与查询最相关的代码片段
"""
import os
import sys
import math

from chroma_client import get_text_embedding, get_chroma_client, init_embedding_client


# ==================== 核心功能函数 ====================

def vector_search(query: str, top_k: int = 5, collection_id: str = None):
    """
    向量检索功能
    
    入参:
        query: string — 自然语言查询
        top_k: int — 返回最相关的几条，默认5
        collection_id: string | null — 可选，指定集合名
    
    出参:
        results: list — 匹配结果列表，每条包含code_chunk, source_url, similarity_score, chunk_index
    """
    # ① 初始化向量库客户端
    chroma_client = get_chroma_client()
    
    # ② 获取集合
    target_collection_id = collection_id if collection_id else "js_code_chunks"
    try:
        collection = chroma_client.get_collection(name=target_collection_id)
    except Exception as e:
        return {"error": f"集合 '{target_collection_id}' 不存在: {e}"}
    
    # ③ 将查询文本向量化
    embedding_client = init_embedding_client()
    emb = get_text_embedding(query, embedding_client)
    if not emb:
        return {"error": "查询文本向量化失败"}
    
    # ④ 执行向量检索
    try:
        res = collection.query(
            query_embeddings=[emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        return {"error": f"向量检索失败: {e}"}
    
    # ⑤ 解析结果
    documents = res.get("documents", [[]])[0]
    ids = res.get("ids", [[]])[0]
    metadatas = res.get("metadatas", [[]])[0]
    distances = res.get("distances", [[]])[0]
    
    results = []
    for chunk_id, content, meta, distance in zip(ids, documents, metadatas, distances):
        # 提取 chunk_index（从ID或metadata中）
        # ID格式通常是 "文件名_chunk_序号"
        chunk_index = 0
        if isinstance(chunk_id, str) and "_chunk_" in chunk_id:
            try:
                chunk_index = int(chunk_id.split("_chunk_")[-1])
            except:
                chunk_index = meta.get("index", 0) if meta else 0
        elif meta:
            chunk_index = meta.get("index", 0)
        
        # 构建 source_url（从metadata的多个可能字段中提取）
        source_url = ""
        if meta:
            # 优先级1: json_source字段（存储的是文件名或URL标识）
            json_source = meta.get("json_source", "")
            if json_source:
                source_url = json_source
            # 优先级2: file_path字段（完整文件路径）
            elif meta.get("file_path"):
                file_path = meta.get("file_path", "")
                source_url = os.path.basename(file_path)
            # 优先级3: 从chunk_id中提取文件名前缀
            elif isinstance(chunk_id, str) and "_chunk_" in chunk_id:
                source_url = chunk_id.split("_chunk_")[0]
        
        # 计算相似度分数(distance转similarity)
        # ChromaDB返回的是L2距离或余弦距离,越小越相似
        # 使用指数衰减函数转换为0-1的相似度分数
        similarity_score = math.exp(-distance)  # e^(-distance),距离0时相似度1,距离越大相似度趋近0
        
        results.append({
            "code_chunk": content,
            "source_url": source_url,
            "similarity_score": round(similarity_score, 4),
            "chunk_index": chunk_index
        })
    
    return results


# ==================== 工具注册信息 ====================
TOOL_INFO = {
    "name": "vector_search",
    "brief": "向量检索工具，在JS代码向量库中搜索相关代码片段。入参：query(string)-自然语言查询, top_k(int)-返回数量默认5, collection_id(string|null)-可选集合名",
    "detail": """【功能说明】
在JS代码向量库中进行语义检索，返回与查询最相关的代码片段。

【入参说明】
- query: string — 自然语言查询（如"sign签名函数"、"加密逻辑"）
- top_k: int — 返回最相关的几条结果，默认5
- collection_id: string | null — 可选，指定要搜索的集合名，不传则搜索默认集合"js_code_chunks"

【出参说明】
返回 results: list，每条结果包含：
  - code_chunk: string — 匹配的代码片段内容
  - source_url: string — 来源文件URL（从metadata的json_source字段构建）
  - similarity_score: float — 相似度分数（0-1，由distance转换）
  - chunk_index: int — 在原文件中是第几块

【调用示例】
{"tool": "vector_search", "query": "sign签名函数", "top_k": 5}
{"tool": "vector_search", "query": "加密逻辑", "top_k": 3, "collection_id": "js_code_chunks"}
""",
    "func": vector_search
}


# ==================== 测试代码 ====================
if __name__ == "__main__":
    print("=== 测试 vector_search 工具 ===")
    
    # 测试1: 基本查询
    query1 = "sign签名函数"
    print(f"\n【查询】{query1}")
    results1 = vector_search(query=query1, top_k=3)
    if isinstance(results1, list):
        print(f"【返回结果数】{len(results1)}")
        for i, r in enumerate(results1, 1):
            print(f"\n结果 {i}:")
            print(f"  相似度: {r['similarity_score']}")
            print(f"  来源: {r['source_url']}")
            print(f"  块序号: {r['chunk_index']}")
            print(f"  代码片段: {r['code_chunk'][:100]}...")
    else:
        print(f"【错误】{results1}")
    
    # 测试2: 指定集合
    query2 = "加密逻辑"
    print(f"\n【查询】{query2}")
    results2 = vector_search(query=query2, top_k=5, collection_id="js_code_chunks")
    if isinstance(results2, list):
        print(f"【返回结果数】{len(results2)}")
    else:
        print(f"【错误】{results2}")
