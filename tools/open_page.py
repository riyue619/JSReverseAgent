# 时间库：用于等一等，让动态JS加载完
import time

from tools.browser_service.browser_manager import is_ready, get_service, init_service


# 只导入需要的3个工具函数（清理冗余导入）



def open_page(url: str) -> dict:
    """
    用浏览器服务打开指定网页，返回页面基本信息和新增资源数量。

    入参：
        url — 要打开的网页地址

    出参（字典）：
        success: bool          — 是否成功打开
        title: str             — 页面标题
        final_url: str         — 最终URL（可能有重定向）
        new_requests_count: int — 打开后新增的网络请求数
        new_scripts_count: int — 打开后新加载的JS文件数
        error: str | None      — 失败原因，成功时为None
    """

    # 第一步：检查浏览器服务是否已启动
    if not is_ready():
        return {
            "success": False,
            "title": "",
            "final_url": "",
            "new_requests_count": 0,
            "new_scripts_count": 0,
            "error": "浏览器服务还没启动，请先初始化 init_service()",
        }

    # 拿到服务实例，后续操作都靠它
    service = get_service()

    # 记录打开页面前的现状
    before_req = len(service.get_requests())
    before_script = len(service.get_scripts())

    # 第二步：导航到目标地址
    try:
        service.run_async(
            service.get_page().goto(url, wait_until="networkidle", timeout=30000)
        )
    except TimeoutError:
        pass
    except Exception as e:
        return {
            "success": False,
            "title": "",
            "final_url": "",
            "new_requests_count": 0,
            "new_scripts_count": 0,
            "error": f"页面导航失败: {e}",
        }

    # 第三步：等待动态JS加载
    time.sleep(2)

    # 第四步：获取页面信息
    title = service.run_async(service.get_page().title())
    final_url = service.get_page().url

    # 第五步：计算新增资源
    new_requests_count = len(service.get_requests()) - before_req
    new_scripts_count = len(service.get_scripts()) - before_script

    return {
        "success": True,
        "title": title,
        "final_url": final_url,
        "new_requests_count": new_requests_count,
        "new_scripts_count": new_scripts_count,
        "error": None,
    }


# ============== 工具元信息（给注册表用） ==============
TOOL_INFO = {
    "name": "open_page",
    "brief": "打开指定URL的网页，获取页面标题和新加载的资源数量（url: 网页地址）",
    "detail": """入参：
    url — 要打开的网页地址（字符串）

出参（字典）：  
    success: bool          — 是否成功打开
    title: str             — 页面标题
    final_url: str         — 最终URL（可能有重定向）
    new_requests_count: int — 打开后新增的网络请求数
    new_scripts_count: int — 打开后新加载的JS文件数
    error: str|None        — 失败原因，成功时为None

调用示例：
    {"tool": "open_page", "url": "https://example.com", "reason": "需要打开目标网站"}""",
    "func": open_page,
}


if __name__ == "__main__":
    # ============== 正确启动方式:单例专用初始化函数 ==============
    # 1. 初始化并启动浏览器服务(无头模式False=显示浏览器窗口)
    init_service(headless=False)

    # 2. 调用页面打开函数
    result = open_page("https://example.com")

    # 3. 打印结果
    print("页面打开结果:", result)