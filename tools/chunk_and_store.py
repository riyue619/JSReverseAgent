import esprima
import logging
import traceback
from typing import List, Tuple

from chroma_client import get_text_embedding, init_embedding_client, init_chroma_db
from tools.temp_cache import get_source

CHUNK_MAX_CHARS = 8000
CHUNK_MIN_CHARS = 50

PRIORITY_NODE_TYPES = {
    "FunctionDeclaration",
    "FunctionExpression",
    "ArrowFunctionExpression",
    "ClassDeclaration",
    "ExportNamedDeclaration",
    "ExportDefaultDeclaration"
}

SUB_NODE_TYPES = {
    "IfStatement", "ForStatement", "WhileStatement",
    "TryStatement", "SwitchStatement", "MethodDefinition"
}


def get_node_name(node) -> str:
    if hasattr(node, "id") and node.id:
        return node.id.name
    elif hasattr(node, "key") and node.key:
        return node.key.name if hasattr(node.key, "name") else str(node.key.value)
    elif node.type == "ArrowFunctionExpression":
        return "arrow_function"
    elif node.type == "FunctionExpression":
        return "anonymous_function"
    else:
        return "unknown"


def split_oversized_by_ast(node, lines, max_len=CHUNK_MAX_CHARS) -> List[str]:
    s_line_1 = node.loc.start.line
    e_line_1 = node.loc.end.line
    s_line_0 = s_line_1 - 1
    e_line_0 = e_line_1
    full_code = "\n".join(lines[s_line_0:e_line_0]).strip()

    if len(full_code) <= max_len:
        return [full_code]

    sub_nodes = []

    def traverse_sub(node_sub):
        if node_sub.type in SUB_NODE_TYPES and hasattr(node_sub, "loc"):
            sub_s_1 = node_sub.loc.start.line
            sub_e_1 = node_sub.loc.end.line
            if s_line_1 <= sub_s_1 and sub_e_1 <= e_line_1:
                sub_s_0 = sub_s_1 - 1
                sub_e_0 = sub_e_1
                sub_code = "\n".join(lines[sub_s_0:sub_e_0]).strip()
                if len(sub_code) >= CHUNK_MIN_CHARS:
                    sub_nodes.append((sub_s_1, sub_e_1, sub_code))

    for k, v in node.__dict__.items():
        if isinstance(v, list):
            for item in v:
                if isinstance(item, esprima.nodes.Node):
                    traverse_sub(item)
        elif isinstance(v, esprima.nodes.Node):
            traverse_sub(v)

    if sub_nodes:
        sub_nodes_sorted = sorted(list(set(sub_nodes)), key=lambda x: x[0])
        return [sub[2] for sub in sub_nodes_sorted if len(sub[2]) <= max_len]

    return split_oversized_by_line(full_code, max_len)


def split_oversized_by_line(code: str, max_len=CHUNK_MAX_CHARS) -> List[str]:
    if not code.strip() or len(code) <= max_len:
        return [code.strip()] if len(code.strip()) >= CHUNK_MIN_CHARS else []

    lines = code.splitlines()
    parts = []
    current = []
    current_len = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        line_len = len(line) + 1

        if len(line) > max_len:
            if current:
                parts.append("\n".join(current).strip())
                current = []
                current_len = 0
            line_chunks = [line[i:i + max_len].strip() for i in range(0, len(line), max_len)]
            parts.extend([c for c in line_chunks if len(c) >= CHUNK_MIN_CHARS])
            continue

        if current_len + line_len > max_len:
            current_block = "\n".join(current).strip()
            if len(current_block) >= CHUNK_MIN_CHARS:
                parts.append(current_block)
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        final_block = "\n".join(current).strip()
        if len(final_block) >= CHUNK_MIN_CHARS:
            parts.append(final_block)

    return [p for p in parts if CHUNK_MIN_CHARS <= len(p) <= max_len]


def get_uncovered_ranges(covered_ranges: List[Tuple[int, int]], total_lines: int) -> List[Tuple[int, int]]:
    if not covered_ranges or total_lines == 0:
        return [(1, total_lines)] if total_lines > 0 else []

    sorted_ranges = sorted(covered_ranges)
    merged = [sorted_ranges[0]]
    for curr in sorted_ranges[1:]:
        last_s, last_e = merged[-1]
        curr_s, curr_e = curr
        if curr_s <= last_e + 1:
            merged[-1] = (last_s, max(last_e, curr_e))
        else:
            merged.append(curr)

    uncovered = []
    if merged[0][0] > 1:
        uncovered.append((1, merged[0][0] - 1))
    for i in range(1, len(merged)):
        prev_e = merged[i - 1][1]
        curr_s = merged[i][0]
        if curr_s > prev_e + 1:
            uncovered.append((prev_e + 1, curr_s - 1))
    if merged[-1][1] < total_lines:
        uncovered.append((merged[-1][1] + 1, total_lines))

    return [(s, e) for s, e in uncovered if s <= e]


def split_js_by_ast_safe(js_code: str, file_path: str = "unknown.js") -> List[dict]:
    chunks = []
    chunk_index = 1
    covered_ranges = []
    processed_line_ranges = []

    try:
        ast = esprima.parseScript(js_code, loc=True, tolerant=True)
        lines = js_code.splitlines()
        total_lines_1based = len(lines)

        def is_line_range_covered(check_range: Tuple[int, int]) -> bool:
            check_s, check_e = check_range
            for (proc_s, proc_e) in processed_line_ranges:
                if proc_s <= check_s and check_e <= proc_e:
                    return True
            return False

        def traverse(node, parent_type: str = ""):
            nonlocal chunk_index
            if parent_type in PRIORITY_NODE_TYPES and node.type in SUB_NODE_TYPES:
                return

            if node.type in PRIORITY_NODE_TYPES and hasattr(node, "loc"):
                s_1 = node.loc.start.line
                e_1 = node.loc.end.line
                current_range = (s_1, e_1)

                if is_line_range_covered(current_range):
                    return

                processed_line_ranges.append(current_range)
                covered_ranges.append(current_range)

                s_0 = s_1 - 1
                e_0 = e_1
                code_block = "\n".join(lines[s_0:e_0]).strip()

                if len(code_block) >= CHUNK_MIN_CHARS:
                    split_parts = split_oversized_by_ast(node, lines, CHUNK_MAX_CHARS)
                    node_name = get_node_name(node)

                    for part in split_parts:
                        chunks.append({
                            "index": chunk_index,
                            "file_path": file_path,
                            "content": part,
                            "node_type": node.type,
                            "node_name": node_name,
                            "line_range": f"{s_1}-{e_1}",
                            "length": len(part),
                            "source": "priority_node"
                        })
                        chunk_index += 1

            for k, v in node.__dict__.items():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, esprima.nodes.Node):
                            traverse(item, parent_type=node.type)
                elif isinstance(v, esprima.nodes.Node):
                    traverse(v, parent_type=node.type)

        traverse(ast)

        uncovered_ranges = get_uncovered_ranges(covered_ranges, total_lines_1based)
        for (s_1, e_1) in uncovered_ranges:
            s_0 = s_1 - 1
            e_0 = e_1
            remaining_code = "\n".join(lines[s_0:e_0]).strip()

            if len(remaining_code) >= CHUNK_MIN_CHARS:
                split_parts = split_oversized_by_line(remaining_code, CHUNK_MAX_CHARS)
                for part in split_parts:
                    chunks.append({
                        "index": chunk_index,
                        "file_path": file_path,
                        "content": part,
                        "node_type": "RemainingCode",
                        "node_name": "remaining",
                        "line_range": f"{s_1}-{e_1}",
                        "length": len(part),
                        "source": "remaining_code"
                    })
                    chunk_index += 1

    except Exception as e:
        logging.error(f"解析{file_path}失败: {e}")
        logging.error(traceback.format_exc())
        fallback_parts = split_oversized_by_line(js_code, CHUNK_MAX_CHARS)
        for part in fallback_parts:
            chunks.append({
                "index": chunk_index,
                "file_path": file_path,
                "content": part,
                "node_type": "Fallback",
                "node_name": "fallback",
                "line_range": "unknown",
                "length": len(part),
                "source": "fallback"
            })
            chunk_index += 1

    def get_start_line(chunk: dict) -> int:
        try:
            line_range = chunk["line_range"]
            if line_range == "unknown":
                return 999999
            start_line = int(line_range.split("-")[0])
            return start_line
        except:
            return 999999

    chunks_sorted = sorted(chunks, key=get_start_line)

    for idx, chunk in enumerate(chunks_sorted, start=1):
        chunk["index"] = idx

    return chunks_sorted


def chunk_and_store(temp_id: str, source_url: str) -> dict:
    """
    从 temp_cache 读取源码，按 AST 切块后向量化入库。

    入参：
        temp_id    — 代码临时编号（字符串）
        source_url — 代码来源 URL（字符串）

    出参（字典）：
        success: bool       — 是否成功
        chunks_count: int   — 切了多少块
        collection_id: str  — 入库后的集合 ID
        error: str|None     — 失败原因，成功时为 None
    """
    try:
        # 1. 从缓存读取源码
        js_code = get_source(temp_id)
        if not js_code:
            return {
                "success": False,
                "chunks_count": 0,
                "collection_id": "",
                "error": f"temp_id '{temp_id}' 在缓存中找不到源码"
            }

        # 2. 按 AST 安全切块
        chunks = split_js_by_ast_safe(js_code, source_url)

        # 3. 初始化 embedding 客户端和 chroma collection
        collection = init_chroma_db()
        collection_id = getattr(collection, "name", "js_code_chunks")

        # 如果代码太短不需要切块，也算成功
        if not chunks:
            return {
                "success": True,
                "chunks_count": 0,
                "collection_id": collection_id,
                "error": None
            }

        embedding_client = init_embedding_client()

        # 4. 遍历每个 chunk，生成 embedding 并存入 chroma
        for chunk in chunks:
            code = chunk.get("content", "").strip()
            if not code:
                continue

            emb = get_text_embedding(code, embedding_client)
            if not emb:
                continue

            chunk_index = chunk.get("index", 0)
            chunk_id = f"{temp_id}_chunk_{chunk_index}"

            metadata = {
                "source_url": source_url,
                "chunk_index": chunk_index,
                "node_type": chunk.get("node_type", ""),
                "line_range": chunk.get("line_range", ""),
                "length": chunk.get("length", 0),
            }

            try:
                collection.add(
                    ids=[chunk_id],
                    embeddings=[emb],
                    documents=[code],
                    metadatas=[metadata]
                )
            except Exception:
                # 单条入库失败不影响整体，继续处理下一个
                continue

        return {
            "success": True,
            "chunks_count": len(chunks),
            "collection_id": collection_id,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "chunks_count": 0,
            "collection_id": "",
            "error": str(e)
        }


TOOL_INFO = {
    "name": "chunk_and_store",
    "brief": "将代码切块并向量化入库，用于后续语义检索（temp_id: 代码临时编号, source_url: 来源URL）",
    "detail": """入参：
    temp_id — 要入库的代码临时编号（字符串，来自 get_script_source 的 temp_id 或 deobfuscate_code 的 new_temp_id）
    source_url — 代码来源URL（字符串，方便后续溯源）

出参（字典）：
    success: bool       — 是否成功
    chunks_count: int   — 切了多少块
    collection_id: str  — 入库后的集合ID，后续检索可用
    error: str|None     — 失败原因，成功时为None

调用示例：
    {"tool": "chunk_and_store", "temp_id": "a1b2c3d4", "source_url": "http://example.com/app.js", "reason": "需要将代码入库以便后续检索"}""",
    "func": chunk_and_store,
}
