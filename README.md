# AI Agent 6 - 智能 JS 逆向工程 Agent

基于 ReAct 框架的 AI 驱动 JavaScript 逆向工程工具，能够自动浏览网页、捕获 JS 代码、注入 Hook、反混淆代码，帮助安全工程师高效分析网站的加密逻辑与请求签名机制。

## 核心能力

- **浏览器自动化** — 基于 Playwright + CDP（Chrome DevTools Protocol）控制 Chromium 浏览器，支持页面打开、网络抓包、JS 脚本捕获、页面交互（点击/输入/滚动）
- **ReAct 推理循环** — AI 自主思考 → 调用工具 → 观察结果 → 循环迭代，直至给出分析结论
- **JS Hook 注入** — 动态拦截目标函数调用，捕获参数、返回值、调用栈
- **代码反混淆** — 对混淆/压缩的 JS 代码进行反混淆分析
- **向量检索** — 使用 ChromaDB + Embedding 模型对 JS 代码片段建立语义索引，支持自然语言检索
- **多模型支持** — 通过 `config.yaml` 一键切换千问/DeepSeek/OpenAI，无需修改代码
- **对话记忆** — 长期对话记忆 + 短期推理记忆，支持多轮复杂分析任务
- **Token 计费统计** — 每轮对话自动统计 Token 消耗与费用

## 架构概览

```
AI_Agent_6/
├── main.py                 # 入口：初始化配置、启动服务、ReAct 循环
├── qwen_client.py          # LLM 客户端：Prompt 构建、API 调用、Token 计费
├── config.yaml             # 模型配置：切换模型只需改 active 字段
├── config_loader.py        # 配置加载器：解析 YAML + 环境变量
├── chroma_client.py        # ChromaDB 客户端：向量存储与检索
├── memory/
│   ├── longMem.py          # 长期记忆：对话历史持久化
│   └── shortMem.py         # 短期记忆：推理过程记录
└── tools/
    ├── tool_registry.py    # 工具注册表：自动扫描并注册所有工具
    ├── browser_service/    # 浏览器服务（单例模式，线程安全）
    │   └── browser_manager.py
    ├── open_page.py        # 打开网页 + 捕获请求/JS
    ├── list_scripts.py     # 列出页面所有 JS 脚本
    ├── get_script_source.py # 获取 JS 脚本源码
    ├── inject_hook.py      # 注入 JS Hook 拦截函数调用
    ├── get_hook_data.py    # 获取 Hook 捕获的数据
    ├── search_requests.py  # 搜索网络请求
    ├── get_request_detail.py # 获取请求详情（含响应体）
    ├── interact_page.py    # 页面交互（点击/输入/滚动）
    ├── deobfuscate_code.py # JS 代码反混淆
    ├── chunk_and_store.py  # JS 代码分块入库
    └── vector_search.py    # 向量语义检索
```

## 快速开始

### 环境要求

- Python >= 3.10
- Node.js >= 18（反混淆功能依赖）
- 支持 OpenAI 兼容 API 的 LLM 服务（千问 / DeepSeek / OpenAI）
- Chromium 浏览器（Playwright 自动安装）

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/riyue619/JSReverseAgent.git
cd JSReverseAgent

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 Playwright 浏览器
playwright install chromium

# 5. 安装 Node.js 反混淆工具
npm install -g synchrony
```

### 配置

1. 创建 `.env` 文件，填入 API Key：

```env
# 千问（默认推荐）
DASHSCOPE_API_KEY=sk-your-key-here

# DeepSeek（可选）
DEEPSEEK_API_KEY=sk-your-key-here

# OpenAI（可选）
OPENAI_API_KEY=sk-your-key-here
```

2. 在 `config.yaml` 中切换模型（可选，默认为千问）：

```yaml
active: "qwen"        # 可选: qwen | deepseek | openai
```

### 运行

```bash
python main.py
```

进入交互式对话界面：

```
你：打开 https://example.com 并分析它的登录加密逻辑
AI：正在打开页面...
    [ReAct 推理过程]
    ...最终给出分析结果
```

输入 `exit` 或 `quit` 退出。

## 工作流程

```
用户提问 → AI 思考（Thought）
          → 判断是否需要工具
            → 需要 → 调用工具（Action）
                   → 观察结果（Observation）
                   → 继续思考...
            → 不需要 → 直接回答
```

AI 可调用的工具包括：
- 打开网页、列出脚本、读取源码
- 注入 JS Hook 拦截加密函数
- 搜索网络请求、获取请求详情
- 页面交互（模拟用户操作触发加密逻辑）
- JS 代码反混淆
- 向量库语义检索已有代码片段

## 配置说明

`config.yaml` 支持三个模型提供商，每个包含：

| 配置项 | 说明 |
|--------|------|
| `chat.base_url` | LLM API 地址 |
| `chat.model` | 模型名称 |
| `chat.api_key_env` | API Key 对应的环境变量名 |
| `embedding.base_url` | Embedding API 地址 |
| `embedding.model` | Embedding 模型名称 |
| `pricing.input` | 输入价格（元/百万 tokens） |
| `pricing.output` | 输出价格（元/百万 tokens） |

切换模型只需修改 `active` 字段，无需更改任何代码。

## 项目特色

- **纯 JSON 通信** — AI 输出格式严格约束为 JSON，保证可解析性
- **单例浏览器服务** — 全局唯一浏览器实例，子线程运行异步事件循环，线程安全
- **工具即插即用** — 新增工具只需在 `tools/` 目录下创建 `.py` 文件并定义 `TOOL_INFO`，启动时自动注册
- **多模型透明切换** — 底层 API 不关心具体模型，`config.yaml` 统一管理
- **推理过程可追溯** — 每一步 AI 推理和工具调用都有完整日志

## License

MIT
