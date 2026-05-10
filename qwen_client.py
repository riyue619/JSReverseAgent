import json
import re
from openai import OpenAI
from tools.tool_registry import scan_tools, get_all_briefs
from config_loader import ModelConfig

# 启动时扫描一次工具，收集所有工具信息
scan_tools()

# 模块级配置，由 main.py 启动时通过 init_config() 注入
_config: ModelConfig = None


def init_config(config: ModelConfig):
    """由 main.py 启动时调用，注入全局模型配置"""
    global _config
    _config = config


def init_llm_client():
    return OpenAI(
        api_key=_config.chat.api_key,
        base_url=_config.chat.base_url
    )


_token_usage = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "reasoning_tokens": 0,
    "total_tokens": 0
}


def calculate_cost(usage: dict) -> dict:
    """根据token用量计算费用

    Args:
        usage: 包含prompt_tokens, completion_tokens, reasoning_tokens的字典

    Returns:
        包含各项费用的字典
    """
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    reasoning_tokens = usage.get("reasoning_tokens", 0)

    # 输入费用
    input_cost = (input_tokens / 1_000_000) * _config.pricing.input

    # 输出费用（包含推理token，推理token属于输出的一部分）
    output_cost = (output_tokens / 1_000_000) * _config.pricing.output

    # 推理token单独计算（按输出价格）
    reasoning_cost = (reasoning_tokens / 1_000_000) * _config.pricing.output

    # 总费用
    total_cost = input_cost + output_cost

    return {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "reasoning_cost": round(reasoning_cost, 6),
        "total_cost": round(total_cost, 6)
    }

def reset_token_usage():
    """重置token累加器，在每轮对话开始时调用"""
    global _token_usage
    _token_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0
    }

def get_token_usage():
    """获取当前累计的token用量"""
    return _token_usage.copy()

def build_prompt(question, tool_results, memory, reasoning):
    prompt = ""
    if memory:
        prompt += "\n=== 历史对话 ==="
        for i, m in enumerate(memory, 1):
            prompt += f"\n第{i}轮：用户={m['Usermessage']} AI={m['AImessage']}"

    if reasoning:
        prompt +="\n=== AI 推理 ==="
        for m in reasoning:
            prompt += f"\n第{m['推理id']}次推理 推理话题:{m['推理话题']}\n推理内容:{m['推理内容']}"
        # print(f"\n第{m['推理id']}次推理 推理话题:{m['推理话题']}\n推理内容:{m['推理内容']}")

    if tool_results:
        prompt += "\n=== 工具返回结果 ==="
        for result in tool_results:
            prompt += f"\n调用序号 {result['调用序号']}{result['工具名']}"
            prompt += f"\n状态：{result['状态说明']}"
            prompt += f"\n调用参数：{json.dumps(result['调用参数'], ensure_ascii=False)}"
            prompt += f"\n返回结果：{json.dumps(result['返回结果'], ensure_ascii=False, indent=2)}"
    prompt += f"\n用户问题：{question}"
    return prompt


def clean_json_string(s):
    """清洗响应 + 修复JSON换行符和未转义双引号问题"""
    if not isinstance(s, str):
        return ""
    s = s.strip()
    s = s.replace("\n", " ").replace("\r", "")

    # 提取JSON对象范围
    match = re.search(r'\{.*\}', s, re.DOTALL)
    if not match:
        return ""

    json_str = match.group(0)

    # 先尝试直接解析
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass

    # 解析失败，尝试修复 message 字段中的未转义双引号
    # 找到 "message":"  的位置
    msg_pattern = re.search(r'"message"\s*:\s*"', json_str)
    if msg_pattern:
        prefix = json_str[:msg_pattern.end()]     # {"tool":"null","message":"
        rest = json_str[msg_pattern.end():]         # ...内容..."}

        # rest 的最后应该是 "} ，从末尾找到它
        # 去掉末尾的 "}  取中间内容
        if rest.endswith('"}'):
            content = rest[:-2]
            # 把内容中的双引号全部转义
            content = content.replace('\\"', '\x00').replace('"', '\\"').replace('\x00', '\\"')
            json_str = prefix + content + '"}'
        elif rest.endswith('"}'):
            # 处理可能有空格的情况
            rstrip = rest.rstrip()
            if rstrip.endswith('"}'):
                content = rest[:rest.rindex('"}')]
                content = content.replace('\\"', '\x00').replace('"', '\\"').replace('\x00', '\\"')
                json_str = prefix + content + '"}'

    return json_str


def call_qwen(prompt: str, client: OpenAI):
    try:
        tool_briefs = get_all_briefs()
        system_prompt = f'''你是专业JS逆向工程师，严格使用ReAct框架进行思考与执行。

一、ReAct标准执行流程
1 Thought思考：分析用户问题，判断现有信息是否足够回答，决定是否需要调用工具
2 Action行动：信息不足调用工具，信息足够直接给出答案
3 Observation观察：接收工具返回的JS代码、加密逻辑、函数片段，如果检索结果为空说明项目中没有相关代码，整合信息继续思考
4 循环直到可以回答用户问题

二、可用工具
{tool_briefs}

三、输出格式必须严格遵守无任何多余文字
调用工具时输出：{{"tool":"工具名","参数名":"参数值","reason":"完整ReAct思考过程"}}
无需任何工具时输出：{{"tool":"null","message":"最终答案内容"}}

规则
1 只输出JSON不输出任何解释文字标点换行
2 检索语句必须精准简短可直接用于代码搜索
3 reason必须清晰说明你的ReAct思考逻辑
4 不编造代码不编造信息
5 必须依赖检索工具获取项目信息
6 如果多次检索都为空应尝试更换关键词或直接告知用户未找到相关代码
7 message字段中如包含双引号必须用反斜杠转义如 \"登录\"
'''
        resp = client.chat.completions.create(
            model=_config.chat.model,
            messages=[{"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        if hasattr(resp, 'usage') and resp.usage:
            usage = resp.usage
            _token_usage["prompt_tokens"] += getattr(usage, 'prompt_tokens', 0)
            _token_usage["completion_tokens"] += getattr(usage, 'completion_tokens', 0)
            _token_usage["total_tokens"] += getattr(usage, 'total_tokens', 0)
            # 提取推理token
            details = getattr(usage, 'completion_tokens_details', None)
            if details:
                _token_usage["reasoning_tokens"] += getattr(details, 'reasoning_tokens', 0) or 0
        # print(resp.choices[0].message.content)
        return {
            "content": resp.choices[0].message.content,
            "finish_reason": resp.choices[0].finish_reason
        }
    except Exception as e:
        return {"content": f"错误：{e}", "finish_reason": "error"}