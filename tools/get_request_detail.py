# 时间库：用于等一等，让CDP响应回来
import time

# 只导入需要的工具函数
from tools.browser_service.browser_manager import get_service, is_ready


async def _get_response_body(cdp, request_id):
    """
    通过CDP命令获取指定请求的响应体内容。

    入参：
        cdp         — CDP会话对象
        request_id  — Chrome内部的请求字符串ID

    出参：
        响应体字符串，二进制内容返回"<binary>"，失败返回None
    """
    try:
        # 调用Chrome调试协议获取响应内容
        result = await cdp.send("Network.getResponseBody", {"requestId": request_id})
        body = result.get("body", "")
        base64_encoded = result.get("base64Encoded", False)

        # 二进制内容直接标记，不返回乱码
        if base64_encoded:
            return "<binary>"

        # 超过10000字符截断，防止返回太大
        if len(body) > 10000:
            return body[:10000] + "...(截断)"

        return body
    except Exception:
        # CDP调用失败或响应不存在，返回None
        return None


def _truncate_text(text):
    """
    文本截断工具：超过10000字符就掐尾加省略号。

    入参：
        text — 原始字符串或None

    出参：
        截断后的字符串或None
    """
    if text is None:
        return None
    if len(text) > 10000:
        return text[:10000] + "...(截断)"
    return text


def get_request_detail(req_id: int) -> dict:
    """
    根据请求的整数编号，查找并返回完整的请求详情（包括响应体）。

    入参：
        req_id — 请求的整数编号（就是 _on_request 里自增的那个 req_id）

    出参（字典）：
        url              — 请求URL
        method           — 请求方法
        request_headers  — 完整请求头
        request_body     — 请求体（POST数据），超过10000字符截断
        response_status  — 响应状态码
        response_headers — 响应头
        response_body    — 响应体，超过10000字符截断，二进制内容返回"<binary>"
        call_stack       — 完整调用栈
        error            — 失败原因，成功时为None
    """

    # 第一步：检查浏览器服务是否已启动
    if not is_ready():
        return {
            "url": "",
            "method": "",
            "request_headers": {},
            "request_body": None,
            "response_status": None,
            "response_headers": None,
            "response_body": None,
            "call_stack": [],
            "error": "浏览器服务还没启动，请先初始化 init_service()",
        }

    # 强制转换 req_id 为整数
    try:
        req_id = int(req_id)
    except (ValueError, TypeError):
        return {
            "req_id": req_id,
            "error": f"req_id 必须是整数，收到: {req_id}",
        }

    # 拿到服务实例，后续操作都靠它
    service = get_service()

    # 第二步：在请求列表里找对应 req_id 的记录
    record = None
    for req in service.get_requests():
        if req.get("req_id") == req_id:
            record = req
            break

    # 找不到就返回错误
    if record is None:
        return {
            "url": "",
            "method": "",
            "request_headers": {},
            "request_body": None,
            "response_status": None,
            "response_headers": None,
            "response_body": None,
            "call_stack": [],
            "error": f"找不到编号为 {req_id} 的请求记录",
        }

    # 第三步：从记录里直接取出已有的字段
    url = record.get("url", "")
    method = record.get("method", "")
    request_headers = record.get("headers", {}) or {}
    request_body = _truncate_text(record.get("post_data"))
    response_status = record.get("status_code")
    response_headers = record.get("response_headers")
    call_stack = record.get("call_stack", []) or []

    # 第四步：通过CDP获取响应体（关键步骤）
    try:
        response_body = service.run_async(
            _get_response_body(service.get_cdp(), record.get("request_id"))
        )
    except Exception as e:
        # CDP获取失败也不崩，标记为None并带个错误提示
        response_body = None

    # 第五步：组装结果返回
    return {
        "url": url,
        "method": method,
        "request_headers": request_headers,
        "request_body": request_body,
        "response_status": response_status,
        "response_headers": response_headers,
        "response_body": response_body,
        "call_stack": call_stack,
        "error": None,
    }


# ============== 工具元信息（给注册表用） ==============
TOOL_INFO = {
    "name": "get_request_detail",
    "brief": "根据请求编号获取完整的请求详情，包括响应体、请求头、调用栈等（req_id: 请求整数编号）",
    "detail": """入参：
    req_id — 请求的整数编号（int）

出参（字典）：
    url: str — 请求URL
    method: str — 请求方法
    request_headers: dict — 完整请求头
    request_body: str|None — 请求体（POST数据），超过10000字符截断
    response_status: int|None — 响应状态码
    response_headers: dict|None — 响应头
    response_body: str|None — 响应体，超过10000字符截断，二进制内容返回"<binary>"
    call_stack: list — 完整调用栈
    error: str|None — 失败原因，成功时为None

调用示例：
    {"tool": "get_request_detail", "req_id": 1, "reason": "需要查看该请求的详细响应内容"}""",
    "func": get_request_detail,
}
