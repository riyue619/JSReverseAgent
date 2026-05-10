import os
import importlib

from memory.shortMem import add_short_memory

_registry = {}


def scan_tools():
    """扫描 tools 目录下所有工具文件，收集 TOOL_INFO 注册到 _registry"""
    tools_dir = os.path.dirname(__file__)
    skip_files = {"__init__.py", "tool_registry.py", "temp_cache.py"}

    for filename in os.listdir(tools_dir):
        if not filename.endswith(".py"):
            continue
        if filename in skip_files:
            continue

        module_name = filename[:-3]
        try:
            module = importlib.import_module(f"tools.{module_name}")
            if hasattr(module, "TOOL_INFO"):
                info = module.TOOL_INFO
                _registry[info["name"]] = info
        except Exception as e:
            print(f"导入工具 {filename} 失败：{e}")


def get_all_briefs() -> str:
    """拿到所有工具的名称+简介，拼成字符串（给提示词用）"""
    lines = []
    for name, info in _registry.items():
        lines.append(f"{name}：{info['brief']}")
    return "\n".join(lines)


def get_detail(name: str) -> str | None:
    """传工具名，拿到详细说明（按需加载用）"""
    info = _registry.get(name)
    return info["detail"] if info else None


def get_func(name: str):
    """传工具名，拿到对应的执行函数（分发调用用）"""
    info = _registry.get(name)
    return info["func"] if info else None


def call_tool(tool_name, data, reasoning, question, tool_results, llm_client, memory):
    """
    通用工具包装器：提取公共字段，调用工具函数，追加结果，重新调用AI。

    入参：
        tool_name    — 工具名称（从AI返回的JSON中提取）
        data         — AI返回的完整JSON字典（包含tool、reason和工具参数）
        reasoning    — 推理过程列表
        question     — 用户原始问题
        tool_results — 工具调用结果列表
        llm_client   — LLM客户端
        memory       — 历史对话记忆
    """
    from qwen_client import build_prompt, call_qwen

    # ① 从注册表找到工具信息
    info = _registry.get(tool_name)
    if info is None:
        return None, tool_results, reasoning

    func = info["func"]

    # ② 提取公共字段
    reason = data.pop("reason", "")
    data.pop("tool", None)

    # ③ 存推理记忆
    reasoning = add_short_memory(reasoning, question, reason)

    # ④ 剩下的全是工具参数，直接传给工具函数
    try:
        result = func(**data)
    except Exception as e:
        result = {"error": f"工具执行失败: {e}"}

    # ⑤ 追加工具结果
    call_index = len(tool_results) + 1
    tool_results.append({
        "调用序号": call_index,
        "工具名": tool_name,
        "状态说明": f"执行成功" if not (isinstance(result, dict) and result.get("error")) else f"执行失败: {result.get('error')}",
        "调用参数": data,
        "返回结果": result,
    })


    # ⑦ 重新调用AI
    prompt = build_prompt(question, tool_results, memory, reasoning)
    new_result = call_qwen(prompt, llm_client)

    return new_result, tool_results, reasoning


if __name__ == "__main__":
    scan_tools()
    print(_registry)
    print("=== 工具简介列表 ===")
    print(get_all_briefs())

    print("\n=== 测试按名称查详情 ===")
    print(get_detail("open_page"))

    print("\n=== 测试按名称拿函数 ===")
    func = get_func("open_page")
    print(f"拿到的函数: {func}")
