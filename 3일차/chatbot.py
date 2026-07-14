import json
import os
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

import certifi
import streamlit as st
import yfinance as yf
from dotenv import load_dotenv
from openai import OpenAI

# 실습폴더 루트의 .env에서 API 키 로드 (3.2 OpenAI_API.ipynb와 동일)
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MODEL = "gpt-4o-mini"
DEFAULT_SYSTEM = (
    "You are a helpful assistant. Use tools when needed. 답변은 한국어로 해."
)


# --- Tool 함수 (3.4 Tool_Calling.ipynb 기반) ---


def get_current_weather(city: str = "Seoul") -> str:
    """도시의 현재 날씨를 조회합니다."""
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.64.1"})
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(cafile=certifi.where())
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode())

        current = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]
        area_name = area.get("areaName", [{}])[0].get("value", city)

        return json.dumps(
            {
                "city": area_name,
                "temp_c": current.get("temp_C"),
                "weather": current.get("weatherDesc", [{}])[0].get("value"),
                "humidity": current.get("humidity"),
                "wind_kmph": current.get("windspeedKmph"),
                "source": "wttr.in",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_us_stock_price(ticker: str) -> str:
    """미국 주식 티커의 최근 가격을 조회합니다."""
    symbol = ticker.strip().upper()
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="2d")
        if hist.empty:
            return json.dumps(
                {"error": f"{symbol} 데이터가 없습니다."}, ensure_ascii=False
            )

        latest = hist.iloc[-1]
        close_price = float(latest["Close"]) if "Close" in latest else None
        open_price = float(latest["Open"]) if "Open" in latest else None

        return json.dumps(
            {
                "ticker": symbol,
                "open": round(open_price, 2) if open_price is not None else None,
                "close": round(close_price, 2) if close_price is not None else None,
                "currency": "USD",
                "source": "yfinance",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "도시의 현재 날씨(기온, 날씨 상태, 습도, 풍속)를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "날씨를 조회할 도시 이름 (예: Seoul, Busan, Tokyo)",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_stock_price",
            "description": "미국 주식 티커의 최근 시가·종가를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "주식 티커 심볼 (예: AAPL, TSLA, MSFT)",
                    }
                },
                "required": ["ticker"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_current_weather": get_current_weather,
    "get_us_stock_price": get_us_stock_price,
}


@st.cache_resource
def get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error(
            f"`.env`에 `OPENAI_API_KEY`를 설정하세요.\n\n경로: `{ROOT / '.env'}`"
        )
        st.stop()
    return OpenAI(api_key=api_key)


def assistant_to_dict(msg):
    data = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        data["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return data


def run_agent(messages, temperature=0.3, max_tokens=None):
    """Tool Calling 루프 — 3.4 run_agent_once 패턴의 멀티턴 버전"""
    client = get_client()
    kwargs = {
        "model": MODEL,
        "temperature": temperature,
        "messages": messages,
        "tools": TOOLS,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    tool_log = []

    while True:
        response = client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        if not msg.tool_calls:
            messages.append(assistant_to_dict(msg))
            return msg.content or "", messages, tool_log

        messages.append(assistant_to_dict(msg))

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments or "{}")
            result = TOOL_FUNCTIONS[fn_name](**fn_args)
            tool_log.append(f"{fn_name}({fn_args})")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )


def is_visible_message(message):
    role = message.get("role")
    if role in ("system", "tool"):
        return False
    if role == "assistant":
        if message.get("tool_calls") and not message.get("content"):
            return False
        return bool(message.get("content"))
    return role == "user"


def init_messages():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": DEFAULT_SYSTEM},
        ]


def main():
    st.set_page_config(page_title="OpenAI Tool 챗봇", page_icon="🤖")
    st.title("🤖 OpenAI Tool 챗봇")
    st.caption("3.4 Tool Calling 실습 기반 · 날씨 · 주식 조회")

    init_messages()

    with st.sidebar:
        st.header("설정")
        temperature = st.slider("temperature", 0.0, 1.0, 0.3, 0.1)
        max_tokens = st.number_input(
            "max_tokens (0 = 제한 없음)", min_value=0, value=0, step=50
        )
        system_prompt = st.text_area("system 메시지", value=DEFAULT_SYSTEM)
        st.markdown("**사용 가능한 Tool**")
        st.markdown("- `get_current_weather` — 도시 날씨 조회")
        st.markdown("- `get_us_stock_price` — 미국 주식 가격 조회")
        if st.button("대화 초기화", use_container_width=True):
            st.session_state.messages = [
                {"role": "system", "content": system_prompt},
            ]
            st.rerun()

    st.session_state.messages[0] = {
        "role": "system",
        "content": system_prompt,
    }

    for message in st.session_state.messages:
        if not is_visible_message(message):
            continue
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("메시지를 입력하세요 (예: 서울 날씨 알려줘 / AAPL 주가는?)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                answer, _, tool_log = run_agent(
                    st.session_state.messages,
                    temperature=temperature,
                    max_tokens=max_tokens if max_tokens > 0 else None,
                )
            if tool_log:
                with st.expander("🔧 호출된 Tool"):
                    for log in tool_log:
                        st.code(log)
            st.markdown(answer)


if __name__ == "__main__":
    main()
