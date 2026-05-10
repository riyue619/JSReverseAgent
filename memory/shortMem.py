
import json
import os

MEMORY_PATH = "./conversation_memory.json"

def load_short_memory_count():
    """加载短期记忆(推理记忆)的总数"""
    if not os.path.exists(MEMORY_PATH):
        return 0
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return len(data)
    except:
        return 0


def add_short_memory(memory_list, user_msg, ai_msg):
    推理话题序号 = load_short_memory_count() + 1
    new_id = len(memory_list) + 1
    item = {
        "msgid": 推理话题序号,
        "推理id":new_id,
        "推理话题": user_msg,
        "推理内容": ai_msg
    }
    memory_list.append(item)
    return memory_list

