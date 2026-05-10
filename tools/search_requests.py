from tools.browser_service.browser_manager import is_ready, get_service, init_service
from tools.open_page import open_page


def search_requests(keyword: str, max_results: int = 20):
    """
    在浏览器捕获的所有网络请求中搜索关键词（模糊匹配）。

    入参：
        keyword     — 搜索关键词，在URL、请求体、请求头中模糊匹配，不区分大小写
        max_results — 最多返回的结果数，默认20

    出参（字典）：
        total_matched: int  — 匹配到的请求总数
        results: list       — 搜索结果列表，每条包含：
                                req_id            请求编号（用于调工具获取完整详情）
                                url               请求URL
                                method            请求方法（GET/POST等）
                                match_positions   关键词匹配位置列表，如 ["url"、"post_data"、"headers"]
                                top_call_stack    调用栈前3项（函数名、文件、行号）
        error: str|None     — 失败原因，成功时为None
    """
    # 1. 校验服务状态
    if not is_ready():
        return {
            "success": False,
            "error": "浏览器服务还没启动，请先初始化 init_service()",
        }

    service = get_service()
    requests = service.get_requests()
    keyword_lower = keyword.lower()

    total_matched = 0  # 总匹配数
    results = []  # 匹配结果列表

    for request in requests:
        # 达到最大返回数，停止
        if total_matched >= max_results:
            break

        # 获取请求数据（小写匹配）
        url = str(request.get("url", "")).lower()
        post_data = str(request.get("post_data", "")).lower()
        headers = str(request.get("headers", "")).lower()

        # 匹配位置
        match_positions = []
        if keyword_lower in url:
            match_positions.append("url")
        if keyword_lower in post_data:
            match_positions.append("post_data")
        if keyword_lower in headers:
            match_positions.append("headers")

        # 只有匹配到了，才加入结果
        if match_positions:
            total_matched += 1
            # 组装单条结果（严格按要求的字段）
            item = {
                "req_id": request.get("req_id", 0),
                "url": request.get("url", ""),  # 返回原始URL，不是小写
                "method": request.get("method", ""),
                "match_positions": match_positions,
                # 取调用栈前3层 ✅ 严格满足要求
                "top_call_stack": request.get("call_stack", [])[:3]
            }
            results.append(item)

    # 最终返回：完全符合你写的出参格式！
    return {
        "total_matched": total_matched,
        "results": results
    }


# ============== 工具元信息（给注册表用） ==============
TOOL_INFO = {
    "name": "search_requests",
    "brief": "在浏览器捕获的网络请求中搜索关键词，返回匹配的请求列表（keyword: 搜索关键词, max_results: 最多返回条数，默认20）",
    "detail": """入参：
    keyword — 搜索关键词，在URL、请求体、请求头中模糊匹配，不区分大小写（字符串）
    max_results — 最多返回的结果数，默认20（整数）

出参（字典）：
    total_matched: int — 匹配到的请求总数
    results: list — 搜索结果列表，每条包含：
        req_id — 请求编号（用于调工具获取完整详情）
        url — 请求URL
        method — 请求方法（GET/POST等）
        match_positions — 关键词匹配位置列表，如 ["url", "post_data", "headers"]
        top_call_stack — 调用栈前3项（函数名、文件、行号）

调用示例：
    {"tool": "search_requests", "keyword": "login", "max_results": 10, "reason": "查找登录相关的网络请求"}""",
    "func": search_requests,
}


if __name__ == '__main__':
    init_service(headless=False)
    open_page("https://example.com")

    # 调用工具
    res = search_requests(keyword="example", max_results=10)
    # 打印结果查看
    print(res)


