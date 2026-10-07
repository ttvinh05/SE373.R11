"""Giữ metadata tool calling Gemini mà ChatOpenAI loại bỏ khi chuyển message.

Google yêu cầu gửi lại extra_content (thought_signature) nguyên vẹn ở lượt sau.
Không tạo chữ ký giả, không sửa nội dung câu hỏi hay kết quả tool.
"""
from langchain_openai import ChatOpenAI


class GeminiChatOpenAI(ChatOpenAI):
    def _create_chat_result(self, response, generation_info=None):
        result = super()._create_chat_result(response, generation_info)
        raw = response if isinstance(response, dict) else response.model_dump()
        for generation, choice in zip(result.generations, raw.get('choices', [])):
            extras = {call['id']: call['extra_content']
                      for call in (choice['message'].get('tool_calls') or [])
                      if call.get('extra_content')}
            if extras:
                generation.message.additional_kwargs['gemini_tool_extras'] = extras
        return result

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        extras = {}
        for message in self._convert_input(input_).to_messages():
            extras.update(message.additional_kwargs.get('gemini_tool_extras', {}))
        for message in payload.get('messages', []):
            for call in message.get('tool_calls', []):
                if call['id'] in extras:
                    call['extra_content'] = extras[call['id']]
        return payload
