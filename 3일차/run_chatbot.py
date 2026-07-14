"""Streamlit 실행 전 Windows SSL 인증서 오류를 우회합니다."""

import ssl
import sys
from pathlib import Path

import certifi


def _patched_create_default_context(
    purpose=ssl.Purpose.SERVER_AUTH, *, cafile=None, capath=None, cadata=None
):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if cafile:
        context.load_verify_locations(cafile=cafile)
    elif capath:
        context.load_verify_locations(capath=capath)
    elif cadata:
        context.load_verify_locations(cadata=cadata)
    else:
        context.load_verify_locations(cafile=certifi.where())
    if purpose == ssl.Purpose.SERVER_AUTH:
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
    return context


ssl.create_default_context = _patched_create_default_context

from streamlit.web import cli as stcli

chatbot_path = Path(__file__).with_name("chatbot.py")
sys.argv = ["streamlit", "run", str(chatbot_path), *sys.argv[1:]]
sys.exit(stcli.main())
