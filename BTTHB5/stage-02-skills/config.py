"""Cấu hình project: hằng số hiển thị, giới hạn thực thi và settings đọc từ .env."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from dotenv import dotenv_values

import paths

PROJECT_NAME = "stage-02-skills"
APP_TITLE = "Stage 02: Skills"
CAPABILITY_TEXT = "Tools: read_file, write_file, list_files. Skills: catalog tự phát hiện từ workspace/skills, model tự load SKILL.md bằng read_file. Không chạy lệnh."

# Giới hạn số lần gọi model trong một lượt chat (ModelCallLimitMiddleware).
MODEL_CALL_LIMIT = 8
# Giới hạn số tool calls trong một lượt chat (ToolCallLimitMiddleware).
TOOL_CALL_LIMIT = 20
# Giới hạn số bước của LangGraph (recursion limit), không phải số tool calls.
RECURSION_LIMIT = 50


@dataclass(frozen=True)
class Settings:
    api_key: str
    model_name: str
    base_url: str | None


def load_settings() -> tuple[Settings | None, list[str]]:
    """Đọc .env của project này. Trả (settings, []) hoặc (None, danh sách biến còn thiếu)."""
    load_dotenv(paths.ENV_PATH, override=False)
    external = os.getenv("LAB_MODEL_ENV_FILE")
    if external:
        # Chỉ chọn cấu hình model, không đưa các credential khác vào environment.
        values = dotenv_values(external, interpolate=False)
        api_key = (values.get("OPENAI_API_KEY") or values.get("GEMINI_API_KEY") or "").strip()
        model_name = (values.get("MODEL_NAME") or values.get("GEMINI_MODEL") or "").strip()
        base_url = (values.get("OPENAI_BASE_URL") or "").strip() or None
        if not base_url and values.get("GEMINI_API_KEY"):
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    else:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model_name = os.getenv("MODEL_NAME", "").strip()
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    missing = [name for name, value in (("OPENAI_API_KEY", api_key), ("MODEL_NAME", model_name)) if not value]
    if missing:
        return None, missing
    return Settings(api_key=api_key, model_name=model_name, base_url=base_url), []
