# 异步IO库：用于处理Playwright的异步操作
import asyncio
# 线程库：用于在独立线程运行异步事件循环，避免阻塞主线程
import threading
# 时间库：用于服务启动超时等待、休眠
import time
# Playwright异步API：核心浏览器自动化工具
from playwright.async_api import async_playwright


# 浏览器服务单例类：全局唯一的浏览器实例，负责抓包、监听网络/JS/页面导航
class BrowserService:
    # 单例实例：保证整个程序只有一个BrowserService对象
    _instance = None

    # 单例构造方法：重写__new__实现全局单例
    def __new__(cls):
        # 首次创建才初始化实例
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 服务是否启动完成标志
            cls._instance._ready = False
            # 异步事件循环对象
            cls._instance._loop = None
            # 运行异步任务的守护线程
            cls._instance._thread = None
            # 线程锁：保证多线程操作数据安全
            cls._instance._lock = threading.Lock()
            # 请求计数器：记录所有网络请求序号
            cls._instance._req_counter = 0
            # 页面导航ID：每次页面跳转自增，区分不同页面的请求/脚本
            cls._instance._nav_id = 0
            # 导航分组：按导航ID存储页面的请求+脚本数据
            cls._instance._nav_groups = {}
        return cls._instance

    # ===================== 新增：线程安全的就绪状态判断 =====================
    def is_ready(self):
        """线程安全的获取服务启动状态"""
        with self._lock:
            return self._ready

    # 【核心异步方法】真正启动浏览器、CDP会话、开启监听
    async def _start_async(self, headless=False):
        # 启动Playwright实例
        self._playwright = await async_playwright().start()
        # 启动Chromium浏览器（无头/有头模式）
        self.browser = await self._playwright.chromium.launch(headless=headless)
        # 创建新页面
        self.page = await self.browser.new_page()
        # 创建CDP会话（Chrome调试协议，用于底层抓包/调试）
        self.cdp = await self.page.context.new_cdp_session(self.page)

        # 存储所有网络请求数据
        self._requests = []
        # 存储所有解析的JS脚本数据
        self._scripts = {}
        # 钩子数据（预留）
        self._hook_data = {}
        # 重置导航分组/计数器
        self._nav_groups = {}
        self._nav_id = 0
        self._req_counter = 0

        # 开启CDP三大核心模块
        # 网络模块：开启抓包，监听请求/响应
        await self.cdp.send("Network.enable")
        # 调试器模块：监听JS脚本解析、执行
        await self.cdp.send("Debugger.enable")
        # 页面模块：监听页面跳转、加载
        await self.cdp.send("Page.enable")

        # 绑定CDP事件回调（监听触发后自动执行对应方法）
        # 监听：浏览器即将发送网络请求 → 捕获请求信息
        self.cdp.on("Network.requestWillBeSent", self._on_request)
        # 监听：浏览器收到服务器响应 → 捕获响应信息
        self.cdp.on("Network.responseReceived", self._on_response)
        # 监听：浏览器解析完成JS脚本 → 捕获JS文件信息
        self.cdp.on("Debugger.scriptParsed", self._on_script_parsed)
        # 监听：页面/主框架跳转 → 记录页面导航信息
        self.cdp.on("Page.frameNavigated", self._on_navigated)

        # 标记服务启动完成
        with self._lock:  # 加锁修改状态
            self._ready = True
        print("[BrowserService] 浏览器服务启动完成")

    # 【对外启动方法】创建子线程运行异步浏览器，等待服务就绪
    def start(self, headless=False):
        # 服务已启动则直接返回
        if self.is_ready():  # 修改：调用安全方法
            print("[BrowserService] 服务已经是启动状态，跳过")
            return

        # 子线程执行函数：创建独立事件循环，运行异步启动逻辑
        def run_in_thread():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            # 执行核心启动异步方法
            self._loop.run_until_complete(self._start_async(headless=headless))
            # 保持事件循环运行
            self._loop.run_forever()

        # 创建守护线程（主线程退出时自动销毁）
        self._thread = threading.Thread(target=run_in_thread, daemon=True)
        self._thread.start()

        # 最多等待5秒，检查服务是否启动完成
        for _ in range(50):
            if self.is_ready():  # 修改：调用安全方法
                break
            time.sleep(0.1)

        # 超时未启动则抛出异常
        if not self.is_ready():  # 修改：调用安全方法
            raise RuntimeError("[BrowserService] 服务启动超时")

    # 【回调方法】捕获浏览器发送的网络请求，解析并存储请求详情
    def _on_request(self, params):
        # 提取请求基础信息
        request_info = params.get("request", {})
        initiator = params.get("initiator", {})

        # 请求计数自增
        self._req_counter += 1

        # 组装请求记录（URL、请求头、请求体、调用栈等）
        record = {
            "req_id": self._req_counter,
            "request_id": params.get("requestId"),
            "url": request_info.get("url"),
            "method": request_info.get("method"),
            "headers": request_info.get("headers"),
            "post_data": request_info.get("postData"),
            "initiator_type": initiator.get("type"),
            "initiator_url": initiator.get("url"),
            "initiator_line": initiator.get("lineNumber"),
            "call_stack": [],
        }

        # 提取请求的JS调用栈信息
        stack = initiator.get("stack", {})
        if stack:
            for frame in stack.get("callFrames", []):
                record["call_stack"].append({
                    "function": frame.get("functionName", "(匿名)"),
                    "file": frame.get("url"),
                    "line": frame.get("lineNumber"),
                    "column": frame.get("columnNumber"),
                })

        # 存入请求列表
        self._requests.append(record)

    # 【回调方法】捕获网络响应，匹配请求并补充响应数据
    def _on_response(self, params):
        try:
            request_id = params.get("requestId")
            response = params.get("response", {})

            # 匹配对应的请求，补充状态码、响应头等信息
            for record in self._requests:
                if record.get("request_id") == request_id:
                    record["status_code"] = response.get("status")
                    record["status_text"] = response.get("statusText")
                    record["response_headers"] = response.get("headers")
                    record["mime_type"] = response.get("mimeType")
                    break
        except Exception:
            pass

    # 【回调方法】捕获解析完成的JS脚本，过滤短脚本并存储信息
    def _on_script_parsed(self, params):
        script_id = params.get("scriptId")

        # 过滤长度<50的无效脚本
        if params.get("length", 0) < 50:
            return

        # 存储JS脚本基础信息
        self._scripts[script_id] = {
            "script_id": script_id,
            "url": params.get("url", ""),
            "start_line": params.get("startLine", 0),
            "end_line": params.get("endLine", 0),
            "length": params.get("length", 0),
            "is_dynamic": not params.get("url"),  # 无URL则为动态JS
            "source": None,  # 脚本源码（延迟加载）
        }

    # 【异步方法】通过CDP获取JS脚本源码，并缓存结果
    async def fetch_script_source(self, script_id):
        script_info = self._scripts.get(script_id)
        # 已缓存源码则直接返回
        if script_info and script_info.get("source") is not None:
            return script_info["source"]

        try:
            # 调用CDP接口获取脚本源码
            result = await self.cdp.send("Debugger.getScriptSource", {
                "scriptId": script_id
            })
            source = result.get("scriptSource", "")
        except Exception:
            source = ""

        # 缓存源码
        if script_info is not None:
            script_info["source"] = source

        return source

    # 【Getter方法】获取浏览器实例
    def get_browser(self):
        return self.browser

    # 【Getter方法】获取页面对象
    def get_page(self):
        return self.page

    # 【Getter方法】获取CDP会话对象
    def get_cdp(self):
        return self.cdp

    # 【Getter方法】获取所有捕获的网络请求
    def get_requests(self):
        return self._requests

    # 【Getter方法】获取所有解析的JS脚本
    def get_scripts(self):
        return self._scripts

    # 【Getter方法】获取钩子数据
    def get_hook_data(self):
        return self._hook_data

    # 【Getter方法】获取按导航分组的请求+脚本数据
    def get_nav_groups(self):
        return self._nav_groups

    # 【Getter方法】获取当前页面导航ID
    def get_current_nav_id(self):
        return self._nav_id

    # 【回调方法】页面主框架跳转时触发，分组存储当前页面数据并重置
    def _on_navigated(self, params):
        frame = params.get("frame", {})
        # 忽略子框架，只监听主页面跳转
        if frame.get("parentId"):
            return

        # 导航ID自增
        self._nav_id += 1
        # 存储当前页面的URL、请求、脚本数据
        self._nav_groups[self._nav_id] = {
            "url": frame.get("url", ""),
            "requests": self._requests,
            "scripts": self._scripts,
        }
        # 重置请求/脚本容器，准备记录下一个页面
        self._requests = []
        self._scripts = {}

    # 【清理方法】清空请求数据+重置计数器
    def clear_requests(self):
        self._requests.clear()
        self._req_counter = 0

    # 【清理方法】清空JS脚本数据
    def clear_scripts(self):
        self._scripts.clear()

    # 【清理方法】清空所有数据+重置计数器
    def clear_all(self):
        self._requests.clear()
        self._scripts.clear()
        self._hook_data.clear()
        self._nav_groups.clear()
        self._nav_id = 0
        self._req_counter = 0

    # 【线程安全方法】主线程调用子线程的异步方法（跨线程执行协程）
    def run_async(self, coro):
        with self._lock:
            if not self._loop or not self._loop.is_running():
                raise RuntimeError("[BrowserService] 服务未启动或事件循环未运行")
            # 提交协程到子线程事件循环
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            # 等待并返回执行结果
            return future.result()

    # 【核心异步方法】关闭浏览器、停止Playwright，重置服务状态
    async def _stop_async(self):
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        # 重置服务标志+单例实例
        with self._lock:
            self._ready = False
        BrowserService._instance = None
        print("[BrowserService] 浏览器服务已关闭")

    # 【对外关闭方法】线程安全关闭服务，停止线程+事件循环
    def stop(self):
        if self._loop and self._loop.is_running():
            # 提交关闭异步任务
            asyncio.run_coroutine_threadsafe(self._stop_async(), self._loop)
            time.sleep(0.5)
            # 停止事件循环
            self._loop.call_soon_threadsafe(self._loop.stop)
        # 等待子线程退出
        if self._thread:
            self._thread.join(timeout=5)


# 全局唯一的服务实例
_service = None

# 【全局方法】初始化并启动浏览器服务
def init_service(headless=False):
    global _service
    _service = BrowserService()
    _service.start(headless=headless)
    return _service

# 【全局方法】获取全局浏览器服务实例
def get_service():
    return _service

# 【全局方法】检查服务是否启动完成
def is_ready():
    # 修复：调用线程安全方法，不直接访问私有属性
    return _service is not None and _service.is_ready()