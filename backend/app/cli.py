"""
cli.py - ISSF 2026 规则问答助手命令行入口（美化版）
负责启动交互式命令行 UI，核心问答逻辑委托给 core.rag_service.RAGService
"""

import os
import sys
import time
import threading
import itertools

# 确保项目根目录可导入
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_script_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from .core.rag_service import RAGService
from .utils import setup_logging

logger, _ = setup_logging(log_name="cli", project_root=_project_root)

# ---------- 终端颜色（兼容 Windows） ----------
try:
    import colorama
    colorama.init()
    _GREEN = colorama.Fore.GREEN
    _RED = colorama.Fore.RED
    _YELLOW = colorama.Fore.YELLOW
    _CYAN = colorama.Fore.CYAN
    _MAGENTA = colorama.Fore.MAGENTA
    _BOLD = colorama.Style.BRIGHT
    _RESET = colorama.Style.RESET_ALL
except Exception:
    _GREEN = _RED = _YELLOW = _CYAN = _MAGENTA = _BOLD = _RESET = ""


def _c(color, text):
    return f"{color}{text}{_RESET}"


# ---------- 加载动画 ----------
class Spinner:
    def __init__(self, message="加载中", interval=0.1):
        self.message = message
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None

    def _spin(self):
        for frame in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            if self._stop.is_set():
                break
            print(f"\r{_CYAN}{frame}{_RESET} {self.message}...", end="", flush=True)
            time.sleep(self.interval)
        print("\r" + " " * (len(self.message) + 10) + "\r", end="", flush=True)

    def start(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        print("\r" + " " * (len(self.message) + 10) + "\r", end="", flush=True)


def _print_banner():
    print()
    print("=" * 58)
    print(_c(_BOLD + _GREEN, "    🏹  ISSF 2026 射击规则问答助手 (美化版 CLI)  "))
    print("=" * 58)
    print()


def _print_init_details(details: dict):
    print(_c(_GREEN, "✅ ") + "初始化成功")
    print(f"   📊 向量数量: {details.get('vector_count', '未知')}")
    print(f"   💾 缓存容量: {details.get('cache_capacity', '未知')} 条（TTL {details.get('cache_ttl_seconds', '未知')}s）")
    print(f"   🤖 LLM: {details.get('llm_model', '未知')}")
    print(f"   🔗 Embedding: {details.get('embedding_model', '未知')}")
    print(f"   📝 日志: {details.get('log_file', '未知')}")
    print()
    print("💡 输入射击规则相关问题，输入 " + _c(_YELLOW, "exit/quit") + " 退出")
    print()


def run_cli_ui():
    _print_banner()

    spinner = Spinner("正在初始化模型与向量库", interval=0.08)
    spinner.start()
    try:
        service = RAGService(project_root=_project_root)
        init_result = service.initialize()
    finally:
        spinner.stop()

    if not init_result["success"]:
        print(_c(_RED, "❌ 初始化失败: ") + init_result["message"])
        return

    details = init_result.get("details", {})
    _print_init_details(details)

    while True:
        try:
            user_input = input(_c(_CYAN, "🔍 请输入您的问题: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n" + _c(_YELLOW, "👋 再见！"))
            break

        if user_input.lower() in ("exit", "quit", "q"):
            print(_c(_YELLOW, "👋 再见！"))
            break

        if not user_input:
            continue

        # 思考动画
        think_spinner = Spinner("正在思考", interval=0.06)
        think_spinner.start()
        t0 = time.time()
        try:
            result = service.ask(user_input)
        finally:
            think_spinner.stop()

        if not result["success"]:
            print(_c(_RED, "❌ 错误: ") + result["message"])
            continue

        data = result.get("data") or {}
        answer = data.get("answer", "")
        from_cache = data.get("from_cache", False)
        latency_ms = data.get("latency_ms", 0)

        cache_tag = _c(_MAGENTA, "⚡缓存 ") if from_cache else ""
        print(_c(_GREEN, f"\n📝 回答{cache_tag}(耗时 {latency_ms}ms):"))
        print("-" * 58)
        print(answer)
        print("-" * 58)
        print()


if __name__ == "__main__":
    run_cli_ui()
