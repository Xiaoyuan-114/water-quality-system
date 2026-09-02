"""
聊天智能体 FastAPI 服务
独立运行在 8001 端口，提供 /chat 流式端点
预测能力复用 ai_api.py 的 make_prediction（import 时会加载模型一次）

启动：
    cd WaterQualityAI
    python chat_main.py
访问：
    http://127.0.0.1:8001/docs       Swagger
    POST http://127.0.0.1:8001/chat  流式聊天
"""
import os
import json
import sys
from typing import List, Optional

from contextlib import asynccontextmanager


# ------------------------------------------------------------
# 启动自检：如果在缺少依赖的 Python 环境里运行（例如裸 `python chat_main.py`
# 命中了 conda base 而没命中项目的 myenv），直接给可读报错和正确命令，
# 而不是抛一个让人误以为"服务坏了"的 ModuleNotFoundError。
# ------------------------------------------------------------
def _verify_runtime():
    missing = []
    for _mod in ("fastapi", "uvicorn", "pydantic", "langchain", "langchain_openai", "pymysql"):
        try:
            __import__(_mod)
        except ModuleNotFoundError as e:
            missing.append(e.name or _mod)
    if not missing:
        return
    print("=" * 70, file=sys.stderr)
    print("[启动失败] 当前 Python 环境缺少依赖，请用项目 conda 环境 myenv 启动。", file=sys.stderr)
    print("  缺失模块: " + ", ".join(missing), file=sys.stderr)
    print("  当前解释器: " + sys.executable, file=sys.stderr)
    print("  正确命令（二选一）:", file=sys.stderr)
    print("    D:\\miniconda\\envs\\myenv\\python.exe chat_main.py", file=sys.stderr)
    print("    conda activate myenv && python chat_main.py", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    sys.exit(1)


_verify_runtime()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chat_config import CHAT_PORT, LLM_CONFIG
from chat_agent import get_chat_response
from chat_tools import (
    get_chat_tools,
    CHAT_STATIC_DIR,
    _ensure_tables,
    create_chat_session,
    list_chat_sessions,
    get_chat_messages,
    get_session_owner,
    add_chat_message,
    delete_chat_session,
    get_last_chart_url,
    clear_last_chart_url,
)


# 切到脚本目录，确保能找到 .pkl 模型文件（ai_api 加载模型时需要）
os.chdir(os.path.dirname(os.path.abspath(__file__)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时确保会话历史表存在，并预热 LLM 连接（TCP+TLS+连接池），
    避免用户第一次对话等冷启动的 2-3 秒。"""
    try:
        _ensure_tables()
    except Exception:
        pass  # 数据库不可用时不阻断启动，会话历史功能会随请求报错
    try:
        async for _ in get_chat_response("hi", None, None):
            break  # 拿到第一个 token 就够了
    except Exception:
        pass  # 预热失败不影响启动
    yield


app = FastAPI(
    title="水质系统聊天智能体",
    description="基于 LangChain Agent 的水质系统对话服务，可查库/做预测/查标准",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS：允许 JSP（Tomcat 8080）和 Streamlit（8501）跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 图表 / 导出文件静态目录（由 chart_report 工具生成，浏览器可直接访问）
os.makedirs(CHAT_STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=CHAT_STATIC_DIR), name="static")


# ============================================================
# 请求/响应模型
# ============================================================
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str
    history: Optional[List[ChatMessage]] = None
    model: Optional[str] = None          # 不传用默认模型
    session_id: Optional[str] = None     # 会话持久化：传了就把消息存库
    client_id: Optional[str] = None      # 浏览器标识，用于区分客户端


class SessionCreate(BaseModel):
    client_id: str
    title: Optional[str] = None


# ============================================================
# 健康检查
# ============================================================
@app.get("/")
def health():
    return {
        "status": "online",
        "service": "水质系统聊天智能体",
        "version": "1.0.0",
        "model": LLM_CONFIG["model"],
        "tools": [t.name for t in get_chat_tools()],
    }


@app.get("/tools")
def list_tools():
    """列出可用工具，方便前端展示"""
    return {
        "tools": [
            {"name": t.name, "description": t.description}
            for t in get_chat_tools()
        ]
    }


# ============================================================
# 会话历史持久化端点
# ============================================================
@app.get("/sessions")
def sessions(client_id: str):
    """列出某客户端的会话历史（按更新时间倒序）"""
    try:
        return {"sessions": list_chat_sessions(client_id)}
    except Exception as e:
        return {"sessions": [], "error": str(e)}


@app.post("/sessions")
def create_session(req: SessionCreate):
    """新建一个会话，返回 session_id"""
    try:
        return create_chat_session(req.client_id, req.title)
    except Exception as e:
        return {"error": str(e)}


@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str, client_id: str):
    """加载某个会话的全部消息（需带本人 client_id，防越权读取）"""
    if get_session_owner(session_id) != client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        return {"messages": get_chat_messages(session_id, client_id)}
    except Exception as e:
        return {"messages": [], "error": str(e)}


@app.delete("/sessions/{session_id}")
def remove_session(session_id: str, client_id: str):
    """删除一个会话及其消息（需带本人 client_id，防越权删除）"""
    if get_session_owner(session_id) != client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        ok = delete_chat_session(session_id, client_id)
        return {"ok": ok}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# /chat 流式端点
# ============================================================
@app.post("/chat")
async def chat(req: ChatRequest):
    """
    流式聊天接口。返回 text/plain 流，前端逐段读取。
    body: {"query": "...", "history": [...], "model": "...", "session_id": "...", "client_id": "..."}
    若带 session_id，会把用户消息和助手回复持久化到 chat_message 表。
    """
    history = [m.model_dump() for m in req.history] if req.history else None
    session_id = req.session_id

    # 先存用户消息（失败不影响聊天）
    if session_id:
        try:
            add_chat_message(session_id, "user", req.query, update_title=True)
        except Exception:
            pass

    async def gen():
        full = ""
        clear_last_chart_url()  # 只记录本次请求真实生成的图
        try:
            async for chunk in get_chat_response(
                req.query, history, req.model
            ):
                if chunk:
                    full += chunk
                    # 显式 yield utf-8 字节，避免 Starlette 默认按 latin-1 编码导致中文乱码
                    yield chunk.encode("utf-8")

            # 正常完成：把本次真实生成的图表 URL 强制附到末尾，
            # 避免模型自己编造不存在的 /static/xxx.png 导致前端破图。
            last_url = get_last_chart_url()
            if last_url and last_url not in full:
                add_line = "\n\n![图表](" + last_url + ")\n"
                full += add_line
                yield add_line.encode("utf-8")
        except Exception as e:
            # 流式过程中出错：把错误也吐出去，前端能看到
            err_msg = f"\n\n[智能体出错] {type(e).__name__}: {e}"
            full += err_msg
            yield err_msg.encode("utf-8")
        finally:
            # 流结束后把助手最终回复持久化（前端能看到完整文字后再存，保证语义完整）
            if session_id and full.strip():
                try:
                    add_chat_message(session_id, "assistant", full)
                except Exception:
                    pass

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    import uvicorn
    print("=" * 55)
    print("  水质系统聊天智能体启动中...")
    print(f"  端口: {CHAT_PORT}")
    print(f"  模型: {LLM_CONFIG['model']}")
    print(f"  Swagger: http://127.0.0.1:{CHAT_PORT}/docs")
    print("  启动后用 Streamlit 前端或 POST /chat 测试")
    print("=" * 55)
    uvicorn.run("chat_main:app", host="127.0.0.1", port=CHAT_PORT, reload=False)
