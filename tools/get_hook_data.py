from tools.browser_service.browser_manager import get_service, is_ready
from tools.inject_hook import _hook_registry


def _truncate(text, max_len):
    """
    字符串截断辅助函数：超过指定长度就掐尾加"..."。

    入参：
        text    — 原始字符串
        max_len — 最大允许长度

    出参：
        截断后的字符串
    """
    if text is None:
        return ""
    text = str(text)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def get_hook_data(hook_id: str, mode: str = "summary") -> dict:
    """
    查看指定Hook捕获的调用数据，支持概要和完整两种模式。

    入参：
        hook_id — Hook编号（来自 inject_hook 的返回值）
        mode    — 查看模式："summary" 概要（默认）/ "raw" 完整记录

    出参（summary模式，字典）：
        hook_id: str              — Hook编号
        function_path: str        — Hook的函数名
        call_count: int           — 总调用次数
        last_call_time: str       — 最近一次调用时间
        last_call_args_preview: str — 最近一次参数摘要（截断到200字符）
        error: str|None           — 失败原因，成功时为None

    出参（raw模式，字典）：
        hook_id: str              — Hook编号
        function_path: str        — Hook的函数名
        call_count: int           — 总调用次数
        records: list             — 调用记录列表，每条包含：
                                      timestamp     调用时间
                                      args          参数值列表（每个值截断到500字符）
                                      return_value  返回值（截断到500字符）
                                      call_stack    调用栈（每行一个字符串）
        error: str|None           — 失败原因，成功时为None
    """

    # 第一步：检查浏览器服务是否已启动
    if not is_ready():
        return {
            "hook_id": hook_id if hook_id and isinstance(hook_id, str) else "",
            "function_path": "",
            "call_count": 0,
            "error": "浏览器服务还没启动，请先调用 open_page 打开页面",
        }

    # 第二步：参数合法性校验
    if not hook_id or not isinstance(hook_id, str):
        return {
            "hook_id": "",
            "function_path": "",
            "call_count": 0,
            "error": "hook_id 不能为空且必须是字符串",
        }

    if mode not in ("summary", "raw"):
        return {
            "hook_id": hook_id,
            "function_path": "",
            "call_count": 0,
            "error": 'mode 必须是 "summary" 或 "raw"',
        }

    if hook_id not in _hook_registry:
        return {
            "hook_id": hook_id,
            "function_path": "",
            "call_count": 0,
            "error": "找不到该Hook编号，请确认hook_id是否正确",
        }

    # 第三步：获取浏览器服务实例
    service = get_service()

    # 从注册表获取函数路径
    function_path = _hook_registry[hook_id]["function_path"]

    try:
        # 第四步：从页面获取 Hook 数据
        js_code = f"""() => {{
            if (!window.__hooks__ || !window.__hooks__['{hook_id}']) {{
                return [];
            }}
            return window.__hooks__['{hook_id}'];
        }}"""
        records = service.run_async(service.get_page().evaluate(js_code))

        if records is None:
            records = []

        call_count = len(records)

        # 第五步：根据 mode 处理数据
        if mode == "summary":
            if records:
                last_record = records[-1]
                last_call_time = last_record.get("timestamp", "")
                last_args = last_record.get("args", [])
                last_call_args_preview = _truncate(str(last_args), 200)
            else:
                last_call_time = ""
                last_call_args_preview = ""

            return {
                "hook_id": hook_id,
                "function_path": function_path,
                "call_count": call_count,
                "last_call_time": last_call_time,
                "last_call_args_preview": last_call_args_preview,
                "error": None,
            }

        else:  # mode == "raw"
            processed_records = []
            for record in records:
                # args：如果存在，对每个元素转字符串并截断到500字符
                raw_args = record.get("args")
                if raw_args is not None:
                    args = [_truncate(str(arg), 500) for arg in raw_args]
                else:
                    args = []

                # return_value：如果存在 returnValue 字段，转字符串截断到500字符
                raw_return = record.get("returnValue")
                if raw_return is not None:
                    return_value = _truncate(str(raw_return), 500)
                else:
                    return_value = None

                # call_stack：如果存在 stack 字段，按 "\n" 分割成列表，去掉空行
                raw_stack = record.get("stack")
                if raw_stack is not None:
                    call_stack = [line for line in str(raw_stack).split("\n") if line.strip()]
                else:
                    call_stack = []

                processed_records.append({
                    "timestamp": record.get("timestamp", ""),
                    "args": args,
                    "return_value": return_value,
                    "call_stack": call_stack,
                })

            return {
                "hook_id": hook_id,
                "function_path": function_path,
                "call_count": call_count,
                "records": processed_records,
                "error": None,
            }

    except Exception as e:
        return {
            "hook_id": hook_id,
            "function_path": function_path if 'function_path' in dir() else "",
            "call_count": 0,
            "error": f"获取Hook数据失败: {e}",
        }


# ============== 工具元信息（给注册表用） ==============
TOOL_INFO = {
    "name": "get_hook_data",
    "brief": "查看指定Hook捕获的调用数据，支持概要和完整两种模式（hook_id: Hook编号, mode: summary/raw，默认summary）",
    "detail": """入参：
    hook_id — Hook编号，来自 inject_hook 的返回值（字符串）
    mode    — 查看模式，可选 "summary"（概要，默认）或 "raw"（完整记录）（字符串）

出参（summary模式，字典）：
    hook_id: str              — Hook编号
    function_path: str        — Hook的函数名
    call_count: int           — 总调用次数
    last_call_time: str       — 最近一次调用时间
    last_call_args_preview: str — 最近一次参数摘要（截断到200字符）
    error: str|None           — 失败原因，成功时为None

出参（raw模式，字典）：
    hook_id: str              — Hook编号
    function_path: str        — Hook的函数名
    call_count: int           — 总调用次数
    records: list             — 调用记录列表，每条包含：
                                  timestamp     调用时间
                                  args          参数值列表（每个值截断到500字符）
                                  return_value  返回值（截断到500字符）
                                  call_stack    调用栈（每行一个字符串）
    error: str|None           — 失败原因，成功时为None

调用示例：
    {"tool": "get_hook_data", "hook_id": "b8958e22", "mode": "summary", "reason": "查看Hook的最新调用情况"}""",
    "func": get_hook_data,
}
