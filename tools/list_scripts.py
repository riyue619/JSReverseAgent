# 从浏览器服务模块导入：获取服务实例 + 检查是否就绪
from tools.browser_service.browser_manager import get_service, is_ready, init_service
from tools.open_page import open_page


def list_scripts(keyword: str = None) -> dict:
    """
    列出浏览器当前页面加载的所有JS文件。

    入参：
        keyword — 可选，按URL关键词过滤，不区分大小写。
                  不传则返回全部脚本。

    出参（字典）：
        total: int      — 符合条件的脚本总数
        scripts: list   — 脚本列表，每条包含：
                            script_id   脚本ID（用于调工具6取源码）
                            url         文件URL，空字符串表示动态/内联代码
                            line_count  代码行数（end_line - start_line）
                            source_type "external"（有URL的外部文件）/ "inline"（内联或动态代码）
        error: str|None — 失败原因，成功时为None
    """

    # 第一步：检查浏览器服务是否已启动，没启动就直接返回错误
    if not is_ready():
        return {
            "total": 0,
            "scripts": [],
            "error": "浏览器服务还没启动",
        }

    try:
        # 第二步：拿到服务实例
        service = get_service()

        # 第三步：取出所有脚本字典（key=script_id, value=脚本信息）
        raw_scripts = service.get_scripts()

        # 第四步：遍历所有脚本，组装成我们需要的格式
        scripts = []
        for script_id, info in raw_scripts.items():
            url = info.get("url", "")
            start_line = info.get("start_line", 0)
            end_line = info.get("end_line", 0)
            is_dynamic = info.get("is_dynamic", False)

            # 判断脚本类型：无URL或动态生成的都算内联
            if is_dynamic or not url:
                source_type = "inline"
            else:
                source_type = "external"

            scripts.append({
                "script_id": script_id,
                "url": url,
                "line_count": end_line - start_line,
                "source_type": source_type,
            })

        # 第五步：如果传了关键词，按URL过滤（不区分大小写）
        if keyword is not None:
            keyword_lower = keyword.lower()
            scripts = [s for s in scripts if keyword_lower in s["url"].lower()]

        # 第六步：返回结果
        return {
            "total": len(scripts),
            "scripts": scripts,
            "error": None,
        }

    except Exception as e:
        # 出了任何意外，兜底返回错误信息
        return {
            "total": 0,
            "scripts": [],
            "error": f"获取脚本列表失败: {e}",
        }


# ============== 工具元信息（给注册表用） ==============
TOOL_INFO = {
    "name": "list_scripts",
    "brief": "列出浏览器当前页面加载的所有JS文件（keyword: 过滤关键词，可选）",
    "detail": """入参：
    keyword — 按URL关键词过滤，不区分大小写（字符串，可选，默认None返回全部）

出参（字典）：
    total: int      — 符合条件的脚本总数
    scripts: list   — 脚本列表，每条包含：
                        script_id   脚本ID（用于调工具取源码）
                        url         文件URL，空字符串表示动态/内联代码
                        line_count  代码行数（end_line - start_line）
                        source_type "external"（有URL的外部文件）/ "inline"（内联或动态代码）
    error: str|None — 失败原因，成功时为None

调用示例：
    {"tool": "list_scripts", "keyword": "jquery", "reason": "想查找包含jquery的脚本"}
    {"tool": "list_scripts", "reason": "查看页面所有加载的JS文件"}""",
    "func": list_scripts,
}

if __name__ == "__main__":
    init_service(headless=False)

    # 2. 打开测试页面
    result = open_page("https://example.com")
    print("页面打开结果:", result)

    # 3. 列出所有 JS 脚本
    scripts = list_scripts()
    print("脚本列表:", scripts)
