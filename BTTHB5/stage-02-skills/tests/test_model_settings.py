from langchain_core.messages import HumanMessage, ToolMessage

from agent import build_model
from config import Settings, load_settings


def test_ui_model_preserves_gemini_tool_signature():
    model = build_model(Settings('fake-key', 'gemini-test', 'https://generativelanguage.googleapis.com/v1beta/openai/'))
    extra = {'google': {'thought_signature': 'provider-signature'}}
    response = {'choices': [{'message': {'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': 'call-1', 'type': 'function', 'function': {'name': 'read_file', 'arguments': '{"path":"data/x.md"}'}, 'extra_content': extra}
    ]}, 'finish_reason': 'tool_calls'}]}
    message = model._create_chat_result(response).generations[0].message
    payload = model._get_request_payload([HumanMessage(content='test'), message, ToolMessage(content='ok', tool_call_id='call-1')])
    assert payload['messages'][1]['tool_calls'][0]['extra_content'] == extra


def test_external_gemini_config_does_not_load_other_credentials(tmp_path, monkeypatch):
    env_file = tmp_path / 'model.env'
    env_file.write_text('GEMINI_API_KEY=fake-key\nGEMINI_MODEL=gemini-test\nUNRELATED_SECRET=do-not-load\n')
    monkeypatch.setenv('LAB_MODEL_ENV_FILE', str(env_file))
    monkeypatch.delenv('UNRELATED_SECRET', raising=False)
    settings, missing = load_settings()
    assert missing == []
    assert settings == Settings('fake-key', 'gemini-test', 'https://generativelanguage.googleapis.com/v1beta/openai/')
    import os
    assert 'UNRELATED_SECRET' not in os.environ
