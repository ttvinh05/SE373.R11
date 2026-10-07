from scripts.gemini_compat import GeminiChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage


def test_preserves_provider_tool_signature_through_history():
    model = GeminiChatOpenAI(model='gemini-test', api_key='fake-key')
    extra = {'google': {'thought_signature': 'fake-provider-signature'}}
    response = {'choices': [{'message': {'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': 'call-1', 'type': 'function', 'function': {'name': 'read_file', 'arguments': '{"path":"data/x.md"}'}, 'extra_content': extra}
    ]}, 'finish_reason': 'tool_calls'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
    message = model._create_chat_result(response).generations[0].message
    payload = model._get_request_payload([HumanMessage(content='test'), message, ToolMessage(content='ok', tool_call_id='call-1')])
    assert payload['messages'][1]['tool_calls'][0]['extra_content'] == extra
    assert payload['messages'][2]['content'] == 'ok'


def test_final_response_with_null_tool_calls():
    model = GeminiChatOpenAI(model='gemini-test', api_key='fake-key')
    result = model._create_chat_result({'choices': [{'message': {'role': 'assistant', 'content': 'done', 'tool_calls': None}, 'finish_reason': 'stop'}]})
    assert result.generations[0].message.content == 'done'
