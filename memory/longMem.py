import json
import os



MEMORY_PATH = "./conversation_memory.json"


def load_memory():
    if not os.path.exists(MEMORY_PATH):
        return []
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except:
        return []


def save_memory(memory_list):
    os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory_list, f, ensure_ascii=False, indent=2)


def add_to_memory(memory_list, user_msg, ai_msg, reasoning):
    new_id = len(memory_list) + 1
    item = {
        "msgid": new_id,
        "Usermessage": user_msg,
        "AImessage": ai_msg,
        "reasoning": reasoning
    }
    memory_list.append(item)
    save_memory(memory_list)
    return memory_list

if __name__ == "__main__":
    memory = load_memory()
    # print("加载的记忆：", memory)
