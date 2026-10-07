from pathlib import Path

import agent
from config import Settings
from scripts.gemini_compat import GeminiChatOpenAI
from scripts.model_runtime import configure_model


def test_runtime_installs_provider_adapter_and_is_idempotent(lab_dirs, monkeypatch):
    original = agent.build_model
    monkeypatch.setattr(agent, 'build_model', original)
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-key')
    monkeypatch.setenv('MODEL_NAME', 'gemini-test')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/')
    settings, missing = configure_model()
    assert not missing
    model = agent.build_model(settings)
    assert isinstance(model, GeminiChatOpenAI)
    installed = agent.build_model
    configure_model()
    assert agent.build_model is installed
