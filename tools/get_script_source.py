# 只导入需要的工具函数
from tools.browser_service.browser_manager import get_service, is_ready, init_service
from tools.list_scripts import list_scripts
from tools.open_page import open_page
from tools.temp_cache import save_source


def get_script_source(script_id: str) -> dict:
    """
    获取指定JS脚本的源码预览，用于快速判断脚本内容。

    入参：
        script_id — 脚本ID（来自 list_scripts 的 script_id）

    出参（字典）：
        temp_id: str      — 临时编号，后续工具可用此ID读取完整源码
        preview: str      — 前1000字符预览，供AI快速判断
        url: str          — 脚本网络地址，空字符串表示动态/内联代码
        length: int       — 完整源码总字符数
        is_dynamic: bool  — 是否为动态生成的JS
        error: str|None   — 失败原因，成功时为None
    """

    # 第一步：检查浏览器服务是否已启动，没启动就直接返回全字段默认值 + error
    if not is_ready():
        return {
            "temp_id": "",
            "preview": "",
            "url": "",
            "length": 0,
            "is_dynamic": False,
            "error": "浏览器服务还没启动，请先初始化 init_service()",
        }

    # 第二步：参数合法性校验
    if not script_id or not isinstance(script_id, str):
        return {
            "temp_id": "",
            "preview": "",
            "url": "",
            "length": 0,
            "is_dynamic": False,
            "error": "script_id 不能为空，且必须是字符串",
        }

    # 第三步：获取服务实例
    service = get_service()

    # 第四步：业务逻辑（获取脚本信息和源码）
    try:
        # 从脚本字典中查找对应 script_id 的信息
        raw_scripts = service.get_scripts()
        script_info = raw_scripts.get(script_id)

        if script_info is None:
            return {
                "temp_id": "",
                "preview": "",
                "url": "",
                "length": 0,
                "is_dynamic": False,
                "error": f"找不到 script_id 为 {script_id!r} 的脚本",
            }

        # 取出脚本 URL
        url = script_info.get("url", "")

        # 动态脚本判断：url 为空字符串则视为动态/内联脚本
        is_dynamic = url == ""

        # 通过异步接口获取完整源码
        source = service.run_async(service.fetch_script_source(script_id))

        if source is None:
            source = ""

    except Exception as e:
        return {
            "temp_id": "",
            "preview": "",
            "url": "",
            "length": 0,
            "is_dynamic": False,
            "error": f"获取脚本源码失败: {e}",
        }

    # 第五步：处理返回数据
    # 生成8位临时编号，并缓存完整源码
    temp_id = save_source(source)

    # 截取前1000字符作为预览
    preview = source[:1000]

    # 统计完整源码字符数
    length = len(source)

    # 第六步：返回结果字典
    return {
        "temp_id": temp_id,
        "preview": preview,
        "url": url,
        "length": length,
        "is_dynamic": is_dynamic,
        "error": None,
    }


# ============== 工具元信息（给注册表用） ==============
TOOL_INFO = {
    "name": "get_script_source",
    "brief": "获取指定JS脚本的源码预览（script_id: 脚本ID）",
    "detail": """入参：
    script_id — 脚本ID（字符串，来自 list_scripts 的 script_id）

出参（字典）：
    temp_id: str      — 临时编号，后续工具可用此ID读取完整源码
    preview: str      — 前1000字符预览，供AI快速判断
    url: str          — 脚本网络地址，空字符串表示动态/内联代码
    length: int       — 完整源码总字符数
    is_dynamic: bool  — 是否为动态生成的JS
    error: str|None   — 失败原因，成功时为None

调用示例：
    {"tool": "get_script_source", "script_id": "12", "reason": "需要查看脚本内容以判断功能"}""",
    "func": get_script_source,
}
if __name__ == "__main__":
    init_service(headless=False)

    # 2. 打开测试页面
    result = open_page("https://example.com")
    print("页面打开结果:", result)

    # 3. 列出脚本
    scripts = list_scripts()
    print("脚本列表:", scripts)

    # 4. 获取脚本源码(需要替换为实际的 script_id)
    if scripts.get("scripts"):
        script_id = scripts["scripts"][0].get("script_id")
        p = get_script_source(script_id)
        print("脚本源码:", p)