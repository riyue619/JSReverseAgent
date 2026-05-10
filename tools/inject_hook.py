# 导入：从 browser_manager 获取服务工具 + uuid 生成 Hook 编号
from tools.browser_service.browser_manager import get_service, is_ready, init_service
from uuid import uuid4

from tools.open_page import open_page

# 模块级缓存：记录所有已注入的 Hook 信息（key=hook_id, value=配置信息）
_hook_registry = {}


def inject_hook(function_path: str, capture_args: bool = True, capture_return: bool = True, capture_stack: bool = True, max_records: int = 50) -> dict:
    """
    在浏览器页面中注入JS Hook，拦截指定函数的调用并记录数据。

    入参：
        function_path — 要Hook的函数路径，如 "window.fetch"、"CryptoJS.MD5"、"XMLHttpRequest.prototype.send"
        capture_args  — 是否记录调用参数，默认True
        capture_return — 是否记录返回值，默认True
        capture_stack  — 是否记录调用栈，默认True
        max_records    — 最多记录几次调用，默认50

    出参（字典）：
        success: bool     — 是否注入成功
        hook_id: str      — Hook编号，用于后续查询Hook捕获的数据
        error: str|None   — 失败原因，成功时为None
    """

    # 第一步：检查浏览器服务是否已启动
    if not is_ready():
        return {
            "success": False,
            "hook_id": "",
            "error": "浏览器服务还没启动，请先调用 open_page 打开页面",
        }

    # 第二步：参数合法性校验
    if not function_path or not isinstance(function_path, str):
        return {
            "success": False,
            "hook_id": "",
            "error": "function_path 不能为空且必须是字符串",
        }

    if not isinstance(max_records, int) or max_records <= 0:
        return {
            "success": False,
            "hook_id": "",
            "error": "max_records 必须是大于0的整数",
        }

    # 第三步：获取浏览器服务实例
    service = get_service()

    # 第四步：生成 hook_id，构造 Hook JS 代码并注入到页面
    hook_id = uuid4().hex[:8]

    # 将 Python 布尔值转为 JS 布尔值字符串（true / false）
    js_capture_args = str(capture_args).lower()
    js_capture_return = str(capture_return).lower()
    js_capture_stack = str(capture_stack).lower()

    hook_js = f"""() => {{
        if (!window.__hooks__) {{
            window.__hooks__ = {{}};
        }}
        window.__hooks__['{hook_id}'] = [];

        var path = '{function_path}';
        var parts = path.split('.');
        var methodName = parts.pop();
        var obj = window;
        for (var i = 0; i < parts.length; i++) {{
            obj = obj[parts[i]];
            if (!obj) {{
                throw new Error('Hook注入失败：路径 "' + path + '" 中的 "' + parts[i] + '" 不存在');
            }}
        }}
        var originalFn = obj[methodName];
        if (!originalFn) {{
            throw new Error('Hook注入失败：函数 "' + path + '" 不存在');
        }}

        obj[methodName] = function() {{
            var record = {{}};
            record.timestamp = new Date().toISOString();

            if ({js_capture_args}) {{
                record.args = [];
                for (var i = 0; i < arguments.length; i++) {{
                    try {{
                        record.args.push(JSON.stringify(arguments[i]));
                    }} catch (e) {{
                        record.args.push(String(arguments[i]));
                    }}
                }}
            }}

            if ({js_capture_stack}) {{
                record.stack = new Error().stack;
            }}

            var result = originalFn.apply(this, arguments);

            if ({js_capture_return}) {{
                if (result && typeof result.then === 'function') {{
                    result.then(
                        function(val) {{
                            try {{
                                record.returnValue = JSON.stringify(val);
                            }} catch (e) {{
                                record.returnValue = String(val);
                            }}
                        }},
                        function(err) {{
                            try {{
                                record.returnValue = 'Promise rejected: ' + String(err);
                            }} catch (e) {{
                                record.returnValue = 'Promise rejected';
                            }}
                        }}
                    );
                }} else {{
                    try {{
                        record.returnValue = JSON.stringify(result);
                    }} catch (e) {{
                        record.returnValue = String(result);
                    }}
                }}
            }}

            window.__hooks__['{hook_id}'].push(record);
            if (window.__hooks__['{hook_id}'].length > {max_records}) {{
                window.__hooks__['{hook_id}'].shift();
            }}

            return result;
        }};

        return true;
    }}"""

    try:
        result = service.run_async(service.get_page().evaluate(hook_js))
        if result is not True:
            return {
                "success": False,
                "hook_id": "",
                "error": f"Hook注入失败：页面返回结果为 {result}",
            }
    except Exception as e:
        return {
            "success": False,
            "hook_id": "",
            "error": f"Hook注入失败: {e}",
        }

    # 第五步：注册到模块级缓存
    _hook_registry[hook_id] = {
        "function_path": function_path,
        "capture_args": capture_args,
        "capture_return": capture_return,
        "capture_stack": capture_stack,
        "max_records": max_records,
    }

    # 第六步：返回成功结果
    return {
        "success": True,
        "hook_id": hook_id,
        "error": None,
    }


# ============== 工具元信息（给注册表用） ==============
TOOL_INFO = {
    "name": "inject_hook",
    "brief": "在浏览器页面中注入JS Hook，拦截指定函数调用并记录数据（function_path: 函数路径, capture_args: 是否记录参数 默认True, capture_return: 是否记录返回值 默认True, capture_stack: 是否记录调用栈 默认True, max_records: 最多记录次数 默认50）",
    "detail": """入参：
    function_path — 要Hook的函数路径，如 "window.fetch"、"CryptoJS.MD5"、"XMLHttpRequest.prototype.send"（字符串）
    capture_args  — 是否记录调用参数，默认True（布尔值）
    capture_return — 是否记录返回值，默认True（布尔值）
    capture_stack  — 是否记录调用栈，默认True（布尔值）
    max_records    — 最多记录几次调用，默认50（整数）

出参（字典）：
    success: bool   — 是否注入成功
    hook_id: str    — Hook编号，用于后续查询Hook捕获的数据
    error: str|None — 失败原因，成功时为None

调用示例：
    {"tool": "inject_hook", "function_path": "window.fetch", "capture_args": true, "capture_return": true, "capture_stack": true, "max_records": 50, "reason": "需要拦截fetch请求观察参数"}""",
    "func": inject_hook,
}

if __name__ == "__main__":
    init_service(headless=False)

    # 2. 打开测试页面
    result = open_page("https://example.com")
    print("页面打开结果:", result)

    # 3. 注入 Hook 拦截函数调用
    p = inject_hook(
        function_path="window.fetch",
        capture_args=True,
        capture_return=True,
        capture_stack=True,
        max_records=10
    )
    print("Hook 注入结果:", p)