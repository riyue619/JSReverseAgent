# 时间库：用于等一等，让动态请求和JS加载完
import time

# 只导入需要的工具函数
from tools.browser_service.browser_manager import get_service, is_ready, init_service
from tools.open_page import open_page


def interact_page(action: str, selector: str = None, text: str = None, direction: str = "down") -> dict:
    """
    对当前页面执行交互操作（获取内容、点击、输入、滚动），返回操作结果。

    入参：
        action    — 操作类型，可选："get_content"（获取页面元素）、"click"（点击）、"type"（输入）、"scroll"（滚动）
        selector  — 目标元素选择器（CSS选择器或 text=xxx），click和type时必填
        text      — 要输入的文字，仅action="type"时必填
        direction — 滚动方向，仅action="scroll"时用，"down"向下滚、"up"向上滚，默认"down"

    出参（字典）：
        成功时：
            get_content: {success: bool, elements: list, error: str|None}
            click/type/scroll: {success: bool, new_requests: int, new_scripts: int, error: str|None}
        失败时：{success: False, error: "失败原因"}
    """

    # 第一步：检查浏览器服务是否已启动
    if not is_ready():
        return {
            "success": False,
            "error": "浏览器服务还没启动，请先初始化 init_service()",
        }

    # 第二步：参数合法性校验，防止传错参数导致操作失败
    if action not in ("get_content", "click", "type", "scroll"):
        return {
            "success": False,
            "error": f"不支持的操作类型: {action}，仅支持 get_content / click / type / scroll",
        }

    if action == "click" and not selector:
        return {
            "success": False,
            "error": "click操作需要提供 selector（目标元素选择器）",
        }

    if action == "type" and (not selector or text is None):
        return {
            "success": False,
            "error": "type操作需要提供 selector 和 text（目标元素和输入内容）",
        }

    if action == "scroll" and direction not in ("up", "down"):
        return {
            "success": False,
            "error": "scroll操作的 direction 必须是 'up' 或 'down'",
        }

    # 拿到服务实例，后续操作都靠它
    service = get_service()

    # 第三步：执行对应操作，用try/except包住，元素找不到或超时也不会崩掉
    try:
        if action == "get_content":
            if selector:
                try:
                    service.run_async(service.get_page().wait_for_selector(selector, timeout=5000))
                except Exception:
                    return {
                        "success": False,
                        "elements": [],
                        "error": f"元素未在5秒内出现: {selector}",
                    }
            # 执行JS，把页面上所有能点的、能输的元素都抓出来，给AI"看"
            js_code = r"""() => {
    const elements = [];
    const tags = ['a', 'button', 'input', 'select', 'textarea'];
    tags.forEach(tag => {
        document.querySelectorAll(tag).forEach((el, i) => {
            // 生成唯一CSS选择器
            let selector = '';
            if (el.id) {
                selector = '#' + el.id;
            } else if (el.name) {
                selector = tag + '[name="' + el.name + '"]';
            } else if (el.className && typeof el.className === 'string' && el.className.trim()) {
                selector = tag + '.' + el.className.trim().split(/\s+/).join('.');
            } else {
                selector = tag + ':nth-of-type(' + (i + 1) + ')';
            }
            elements.push({
                tag: tag,
                text: (el.innerText || el.value || el.placeholder || '').substring(0, 50),
                selector: selector,
                type: el.type || null
            });
        });
    });
    return elements;
}"""
            elements = service.run_async(service.get_page().evaluate(js_code))
            return {
                "success": True,
                "elements": elements,
                "error": None,
            }

        # click、type、scroll 都需要算新增资源，先记一下操作前的老底
        before_req = len(service.get_requests())
        before_script = len(service.get_scripts())

        if action == "click":
            try:
                service.run_async(service.get_page().wait_for_selector(selector, timeout=5000))
            except Exception:
                pass  # 等待超时，继续尝试点击
            service.run_async(service.get_page().click(selector, timeout=5000))
        elif action == "type":
            try:
                service.run_async(service.get_page().wait_for_selector(selector, timeout=5000))
            except Exception:
                pass  # 等待超时，继续尝试输入
            service.run_async(service.get_page().fill(selector, text, timeout=5000))
        elif action == "scroll":
            # 根据方向算滚动像素，down往下滚500，up往上滚-500
            scroll_y = 500 if direction == "down" else -500
            service.run_async(service.get_page().evaluate(f"window.scrollBy(0, {scroll_y})"))

        # 等2秒，让操作触发的动态请求和JS加载完
        time.sleep(2)

        # 算一下新增了多少资源
        new_requests = len(service.get_requests()) - before_req
        new_scripts = len(service.get_scripts()) - before_script

        return {
            "success": True,
            "new_requests": new_requests,
            "new_scripts": new_scripts,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"{action}操作失败: {e}",
        }


# ============== 工具元信息（给注册表用） ==============
TOOL_INFO = {
    "name": "interact_page",
    "brief": "对当前页面执行交互操作，返回操作结果（action: get_content/click/type/scroll, selector: CSS选择器, text: 输入内容, direction: up/down）",
    "detail": """入参：
    action    — 操作类型，可选："get_content"（获取页面元素）、"click"（点击）、"type"（输入）、"scroll"（滚动）（字符串）
    selector  — 目标元素选择器（CSS选择器或 text=xxx），click和type时必填（字符串，可选）
    text      — 要输入的文字，仅action="type"时必填（字符串，可选）
    direction — 滚动方向，仅action="scroll"时用，"down"向下滚、"up"向上滚，默认"down"（字符串，可选）

出参（字典）：
    get_content返回：
        success: bool   — 是否成功
        elements: list  — 页面可交互元素列表
        error: str|None — 失败原因，成功时为None
    click/type/scroll返回：
        success: bool   — 是否成功
        new_requests: int — 操作后新增的网络请求数
        new_scripts: int  — 操作后新加载的JS文件数
        error: str|None   — 失败原因，成功时为None
    失败时：
        success: False  — 操作失败
        error: str      — 失败原因

调用示例：
    {"tool": "interact_page", "action": "get_content", "reason": "需要查看页面有哪些可交互元素"}
    {"tool": "interact_page", "action": "click", "selector": "button#submit", "reason": "点击提交按钮"}
    {"tool": "interact_page", "action": "type", "selector": "input#username", "text": "admin", "reason": "在用户名输入框填入账号"}
    {"tool": "interact_page", "action": "scroll", "direction": "down", "reason": "向下滚动页面加载更多内容"}""",
    "func": interact_page,
}


if __name__ == "__main__":
    # 1. 初始化并启动浏览器服务
    init_service(headless=False)

    # 2. 打开测试页面
    result = open_page("https://example.com")
    print("页面打开结果:", result)

    # 3. 获取服务实例(用来拿网络请求)
    service = get_service()

    # ============== 关键步骤:输入前,保存【旧的请求列表】 ==============
    old_requests = service.get_requests().copy()  # 复制一份,避免引用覆盖

    # 4. 执行交互操作
    input_result = interact_page(
        action="get_content"
    )
    print("页面内容获取结果:", input_result)
