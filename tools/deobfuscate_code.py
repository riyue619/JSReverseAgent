import os
import tempfile
import subprocess

from tools.browser_service.browser_manager import init_service
from tools.get_script_source import get_script_source
from tools.list_scripts import list_scripts
from tools.open_page import open_page
from tools.temp_cache import get_source, save_source


def deobfuscate_code(temp_id: str) -> dict:
    """
    对JS代码进行反混淆处理，调用 synchrony 还原被混淆的代码。

    入参：
        temp_id — 原始代码的临时编号（来自 get_script_source 的 temp_id）

    出参（字典）：
        new_temp_id: str       — 反混淆后代码的新临时编号
        original_temp_id: str  — 原始代码的临时编号（便于追溯对应关系）
        preview: str           — 反混淆后代码的前1000字符预览
        original_length: int   — 原始代码字符数
        cleaned_length: int    — 反混淆后代码字符数
        success: bool          — 是否成功
        error: str|None        — 失败原因，成功时为None
    """
    # 第1步：参数校验
    if not temp_id or not isinstance(temp_id, str):
        return {
            "new_temp_id": "",
            "original_temp_id": temp_id if isinstance(temp_id, str) else "",
            "preview": "",
            "original_length": 0,
            "cleaned_length": 0,
            "success": False,
            "error": "temp_id 必须为非空字符串",
        }

    # 第2步：从共享缓存读源码
    original_code = get_source(temp_id)
    if original_code is None:
        return {
            "new_temp_id": "",
            "original_temp_id": temp_id,
            "preview": "",
            "original_length": 0,
            "cleaned_length": 0,
            "success": False,
            "error": "找不到该temp_id对应的源码，请确认temp_id是否正确",
        }

    input_path = None
    output_path = None
    try:
        # 第3步：写临时输入文件
        tmp = tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w", encoding="utf-8")
        tmp.write(original_code)
        tmp.close()
        input_path = tmp.name
        output_path = input_path.replace(".js", "_out.js")

        # 第4步：subprocess 调用 synchrony
        cmd = ["synchrony", "deobfuscate", input_path, "-o", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)

        # 第5步：处理结果
        if result.returncode != 0:
            stderr = result.stderr
            error_msg = stderr.strip() if stderr.strip() else "synchrony 执行失败"
            return {
                "new_temp_id": "",
                "original_temp_id": temp_id,
                "preview": "",
                "original_length": len(original_code),
                "cleaned_length": 0,
                "success": False,
                "error": error_msg,
            }

        # 从输出文件读取反混淆后的代码
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            with open(output_path, 'r', encoding='utf-8') as f:
                cleaned_code = f.read()
        else:
            # 降级处理：输出文件不存在或为空，返回原始代码
            new_temp_id = save_source(original_code)
            return {
                "new_temp_id": new_temp_id,
                "original_temp_id": temp_id,
                "preview": original_code[:1000],
                "original_length": len(original_code),
                "cleaned_length": len(original_code),
                "success": True,
                "error": None,
            }

        # 第6步：存入共享缓存
        new_temp_id = save_source(cleaned_code)

        # 第8步：返回结果字典
        return {
            "new_temp_id": new_temp_id,
            "original_temp_id": temp_id,
            "preview": cleaned_code[:1000],
            "original_length": len(original_code),
            "cleaned_length": len(cleaned_code),
            "success": True,
            "error": None,
        }

    except subprocess.TimeoutExpired:
        return {
            "new_temp_id": "",
            "original_temp_id": temp_id,
            "preview": "",
            "original_length": len(original_code),
            "cleaned_length": 0,
            "success": False,
            "error": "反混淆超时，代码可能过大或过于复杂",
        }

    except FileNotFoundError:
        return {
            "new_temp_id": "",
            "original_temp_id": temp_id,
            "preview": "",
            "original_length": len(original_code),
            "cleaned_length": 0,
            "success": False,
            "error": "请先安装：npm install -g deobfuscator",
        }

    except Exception as e:
        return {
            "new_temp_id": "",
            "original_temp_id": temp_id,
            "preview": "",
            "original_length": len(original_code) if original_code else 0,
            "cleaned_length": 0,
            "success": False,
            "error": f"反混淆失败: {e}",
        }

    finally:
        # 第7步：清理临时文件
        if input_path and os.path.exists(input_path):
            os.unlink(input_path)
        if output_path and os.path.exists(output_path):
            os.unlink(output_path)


# ============== 工具元信息（给注册表用） ==============
TOOL_INFO = {
    "name": "deobfuscate_code",
    "brief": "将指定JS脚本的源码进行反混淆处理（temp_id: 临时编号）",
    "detail": """入参：
    temp_id— 临时编号（字符串，来自 get_script_source的 temp_id）

出参（字典）：
    new_temp_id: str       — 反混淆临时编号，后续工具可用此ID读取完整反混淆代码
    original_temp_id: str  — 原始代码的临时编号（便于追溯对应关系）
    preview: str           — 反混淆后代码的前1000字符预览
    original_length: int   — 原始代码字符数
    cleaned_length: int    — 反混淆后代码字符数
    success: bool          — 是否成功
    error: str|None        — 失败原因，成功时为None

调用示例：
    {"tool": "deobfuscate_code", "temp_id": "12", "reason": "需要反混淆代码"}""",
    "func": deobfuscate_code,
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
        temp_id = p.get('temp_id')
        print("脚本源码:", p)
        
        # 5. 从缓存获取源码
        z = get_source(f"{temp_id}")
        print("缓存源码:", z)

        # 6. 反混淆代码
        a = deobfuscate_code(temp_id)
        print("反混淆结果:", a)