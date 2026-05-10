import json

from dotenv import load_dotenv
from config_loader import load_config
from qwen_client import init_config, init_llm_client, build_prompt, call_qwen, clean_json_string, get_token_usage, calculate_cost
from memory.longMem import load_memory, add_to_memory
from tools.tool_registry import call_tool
from tools.browser_service.browser_manager import init_service
from chroma_client import init_embedding_config

# ① 加载 .env 环境变量
load_dotenv()

# ② 加载模型配置（切换模型只需改 config.yaml 的 active 字段）
config = load_config()

# ③ 注入配置到各模块
init_config(config)
init_embedding_config(config)

# ④ 初始化服务和客户端
llm_client = init_llm_client()
init_service(headless=False)




def chat(question):
    memory = load_memory()
    reasoning = []      # 只存AI的推理思维过程
    tool_results = []   # 存所有工具的执行结果
    prompt = build_prompt(question, tool_results, memory, reasoning)
    result = call_qwen(prompt, llm_client)

    MAX_ROUND = 1000
    for round_idx in range(MAX_ROUND):
        try:
            clean = clean_json_string(result["content"])
            data = json.loads(clean)
            print(f"************************************************************************\nAI的推理:{data.get('reason', '')}\nAI调用工具:{data.get('tool', '')}\n调用工具参数:{data}\n************************************************************************")

            tool = data.get("tool")

            if tool == "null":
                ans = data["message"]
                add_to_memory(memory, question, ans, reasoning)
                usage = get_token_usage()
                cost = calculate_cost(usage)
                print(f"\n{'=' * 50}")
                print(f"本轮对话Token统计:")
                print(f"  输入Token:   {usage['prompt_tokens']}")
                print(f"  输出Token:   {usage['completion_tokens']}")
                print(f"  推理Token:   {usage['reasoning_tokens']}")
                print(f"  总Token:     {usage['total_tokens']}")
                print(f"-" * 50)
                print(f"本轮对话费用统计:")
                print(f"  输入费用:    ¥{cost['input_cost']:.6f}")
                print(f"  输出费用:    ¥{cost['output_cost']:.6f}")
                print(f"  推理费用:    ¥{cost['reasoning_cost']:.6f}")
                print(f"  总费用:      ¥{cost['total_cost']:.6f}")
                print(f"{'=' * 50}")
                return ans

            else:
                # 通用工具调用
                result, tool_results, reasoning = call_tool(
                    tool, data, reasoning, question, tool_results, llm_client, memory
                )
                if result is None:
                    return f"未知工具: {tool}"
        except Exception as e:
            print(f"调试信息：result={result}")
            print(f"调试信息：clean={clean}")
            return f"解析失败：{str(e)}"




if __name__ == "__main__":
    while True:
        q = input("你：")
        if q in ("exit", "quit"):
            break
        ans = chat(q)
        print("AI：", ans)