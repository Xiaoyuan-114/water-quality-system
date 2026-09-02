"""
聊天智能体层（核心）
LangChain create_agent + astream_events 流式输出
架构复用生产实习项目，针对水质系统定制 system prompt
"""
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage

from chat_config import LLM_CONFIG
from chat_tools import get_chat_tools


# ============================================================
# 系统提示词：定义智能体的角色和行为边界
# ============================================================
SYSTEM_PROMPT = """你是一个「水质安全智能助手」，集成在某大学的水质AI检测系统中。
你可以通过工具查询系统的 MySQL 数据库、调用 AI 模型做水质预测。

你能做的事（必须通过工具）：
1. 查询历史检测记录（query_records）
2. 查询水质预警日志（query_alerts）
3. 对 9 项水质指标做 AI 预测（predict_water）
4. 查询水质标准限值 / 水源信息（query_standards）
5. 自动把检测记录与标准逐项对照，指出超标项并给建议（standards_check）
6. 分析水质趋势并对未来几天做简单预测（trend_analysis）
7. 生成图表（占比/水源对比/趋势）或导出 CSV（chart_report）

回答规范：
- 用户问的是数据/查询 → 调对应工具，把工具返回的关键信息整理成简洁中文，别原样贴 JSON。
- 用户给了水质数值想做预测 → 调 predict_water，把结果用通俗语言解释（安全/不安全、概率、等级、建议）。
- 用户问标准或合规 → 调 query_standards / standards_check，用表格或列表呈现指标范围并标注是否超标。
- 用户问趋势/走势 → 调 trend_analysis，给出方向与简单预测；如需可视再调 chart_report。
- 用户想看图或导出 → 调 chart_report；**图片或下载链接只能来自工具返回，并原样保留在回答末尾**（格式：![说明](/static/xxx.png) 或 [下载 CSV](/static/xxx.csv)）。
- **严禁编造不存在的图片、链接、URL。** 若工具没返回图片/下载链接，就不要生成任何 URL 或 markdown 图片语法。
- 用户闲聊或问系统能力 → 友好介绍你能做什么，举几个例子。
- 涉及「安全」结论要谨慎，给出概率和等级，必要时建议复查或深度处理。
- **全程只用简体中文回答**（专业术语可保留英文对照）；不要用泰语、英文或其他语言开场或混用。"""


# ============================================================
# LLM 与 Agent 实例（按模型名缓存）
# ============================================================
_llm_cache = {}
_agent_cache = {}


def _get_llm(model: str = None, temperature: float = None) -> ChatOpenAI:
    """构建 LLM，按 model 缓存"""
    m = model or LLM_CONFIG["model"]
    t = temperature if temperature is not None else LLM_CONFIG["temperature"]
    key = (m, t)
    if key not in _llm_cache:
        _llm_cache[key] = ChatOpenAI(
            model=m,
            temperature=t,
            api_key=LLM_CONFIG["api_key"],
            base_url=LLM_CONFIG["base_url"],
            streaming=True,
        )
    return _llm_cache[key]


def _get_agent(model: str = None):
    """构建 agent，按 model 缓存（agent 绑定工具）"""
    m = model or LLM_CONFIG["model"]
    if m not in _agent_cache:
        llm = _get_llm(m)
        tools = get_chat_tools()
        _agent_cache[m] = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )
    return _agent_cache[m]


# ============================================================
# 流式输出主函数：供 FastAPI /chat 调用
# ============================================================
async def get_chat_response(
    query: str,
    history: list = None,
    model: str = None,
):
    """
    流式生成器：逐段 yield 文本片段。
    history: [{"role":"user","content":"..."},{"role":"assistant","content":"..."}]
    用 astream_events v2 抓 on_chat_model 流式 token + on_tool_end 工具结果。
    """
    agent = _get_agent(model)

    # 把历史消息转成 LangChain 消息格式
    messages = []
    if history:
        for h in history:
            role = h.get("role")
            content = h.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    # 当前问题
    messages.append(HumanMessage(content=query))

    # astream + stream_mode="messages"。按“模型消息”缓冲：一条消息可能先流内容、
    # 后才出现 tool_call_chunks（模型准备调工具前的前言/思考），所以直接把整条消息
    # 攒起来，只有“不是工具调用消息”的那条（即最终回答）才放出去，
    # 彻底避免把调工具前的中间文本（有时是泰文/英文乱入）吐给用户。
    current_id = None
    pending = ""
    discard_msg = False

    async for msg, meta in agent.astream(
        {"messages": messages}, stream_mode="messages"
    ):
        if meta.get("langgraph_node") != "model":
            continue
        mid = getattr(msg, "id", None)
        if mid and mid != current_id:
            # 上一条消息结束：若不丢弃则输出其累积文本
            if pending and not discard_msg:
                yield pending
            current_id = mid
            pending = ""
            discard_msg = False
        content = getattr(msg, "content", "")
        if content:
            pending += content
        if getattr(msg, "tool_calls", None) or getattr(msg, "tool_call_chunks", None):
            discard_msg = True

    # 收尾：输出最后一条非工具消息（即最终回答）
    if pending and not discard_msg:
        yield pending


# ============================================================
# 非流式调用（备用，给调试或前端非流式场景）
# ============================================================
async def get_chat_response_sync(query: str, history: list = None, model: str = None) -> str:
    """一次性返回完整文本"""
    buf = ""
    async for chunk in get_chat_response(query, history, model):
        buf += chunk
    return buf
