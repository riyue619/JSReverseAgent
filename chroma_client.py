import json
import os
import logging
import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from config_loader import ModelConfig

logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
load_dotenv()

# 模块级配置，由 main.py 启动时通过 init_embedding_config() 注入
_config: ModelConfig = None


def init_embedding_config(config: ModelConfig):
    """由 main.py 启动时调用，注入全局模型配置"""
    global _config
    _config = config

def get_chroma_client():
    """获取ChromaDB客户端实例"""
    # 使用相对于本文件的绝对路径,确保无论从何处运行都能找到
    db_path = os.path.join(os.path.dirname(__file__), "js_code_vector_db")
    return chromadb.PersistentClient(
        path=db_path,
        settings=chromadb.Settings(anonymized_telemetry=False)
    )

def init_chroma_db():
    # 使用相对于本文件的绝对路径,确保无论从何处运行都能找到
    db_path = os.path.join(os.path.dirname(__file__), "js_code_vector_db")
    client = chromadb.PersistentClient(
        path=db_path,
        settings=chromadb.Settings(anonymized_telemetry=False)
    )
    collection = client.get_or_create_collection(
        name="js_code_chunks",
        metadata={"description": "JS代码块向量库"}
    )
    return collection

def init_embedding_client():
    return OpenAI(
        api_key=_config.embedding.api_key,
        base_url=_config.embedding.base_url
    )


def get_text_embedding(text: str, client: OpenAI):
    try:
        response = client.embeddings.create(
            input=text,
            model=_config.embedding.model
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ 向量化失败：{e}")
        return None

