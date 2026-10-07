"""Cấu hình model cho launcher; không thay mã nguồn agent/tool của lab."""
import os
from pathlib import Path

from dotenv import dotenv_values


def configure_model(env_file: Path | None = None):
    if env_file:
        values = dotenv_values(env_file, interpolate=False)
        for target, source in [('OPENAI_API_KEY', 'GEMINI_API_KEY'), ('MODEL_NAME', 'GEMINI_MODEL')]:
            value = values.get(target) or values.get(source)
            if value:
                os.environ[target] = value
        base = values.get('OPENAI_BASE_URL')
        if not base and values.get('GEMINI_API_KEY'):
            base = 'https://generativelanguage.googleapis.com/v1beta/openai/'
        if base:
            os.environ['OPENAI_BASE_URL'] = base
    import agent
    from config import load_settings
    from scripts.gemini_compat import GeminiChatOpenAI
    if getattr(agent.build_model, "_lab_gemini_compatible", False):
        return load_settings()
    original = agent.build_model

    def compatible_model(settings):
        if settings.base_url and 'generativelanguage.googleapis.com' in settings.base_url:
            return GeminiChatOpenAI(model=settings.model_name, api_key=settings.api_key, base_url=settings.base_url)
        return original(settings)

    # Adapter provider tại launcher, không thay system prompt, tools hay agent.py.
    compatible_model._lab_gemini_compatible = True
    agent.build_model = compatible_model
    return load_settings()
