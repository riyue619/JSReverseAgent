"""
模型配置加载器
从 config.yaml 读取配置，解析环境变量中的 API Key，
返回统一的 ModelConfig 对象供各模块使用。
"""
import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ChatConfig:
    """对话模型配置"""
    base_url: str
    model: str
    api_key: str


@dataclass
class EmbeddingConfig:
    """Embedding 模型配置"""
    base_url: str
    model: str
    api_key: str


@dataclass
class PricingConfig:
    """计费单价（元/百万tokens）"""
    input: float
    output: float


@dataclass
class ModelConfig:
    """统一的模型配置，包含对话、Embedding、计费三部分"""
    provider_name: str
    chat: ChatConfig
    embedding: EmbeddingConfig
    pricing: PricingConfig


def load_config(config_path: str = None) -> ModelConfig:
    """
    加载模型配置。

    Args:
        config_path: config.yaml 的路径，默认取本文件同级的 config.yaml

    Returns:
        ModelConfig 对象，包含当前激活的提供商全部配置

    Raises:
        FileNotFoundError: config.yaml 不存在
        KeyError: active 指向的提供商配置缺失
        ValueError: 环境变量中的 API Key 未设置或为空
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    active = raw["active"]
    provider = raw["providers"][active]

    # 从环境变量解析 API Key
    chat_api_key = os.getenv(provider["chat"]["api_key_env"], "")
    emb_api_key = os.getenv(provider["embedding"]["api_key_env"], "")

    if not chat_api_key:
        raise ValueError(
            f"聊天模型 API Key 未设置！请在 .env 中配置 "
            f"{provider['chat']['api_key_env']} 环境变量"
        )
    if not emb_api_key:
        raise ValueError(
            f"Embedding 模型 API Key 未设置！请在 .env 中配置 "
            f"{provider['embedding']['api_key_env']} 环境变量"
        )

    return ModelConfig(
        provider_name=active,
        chat=ChatConfig(
            base_url=provider["chat"]["base_url"],
            model=provider["chat"]["model"],
            api_key=chat_api_key,
        ),
        embedding=EmbeddingConfig(
            base_url=provider["embedding"]["base_url"],
            model=provider["embedding"]["model"],
            api_key=emb_api_key,
        ),
        pricing=PricingConfig(
            input=provider["pricing"]["input"],
            output=provider["pricing"]["output"],
        ),
    )
