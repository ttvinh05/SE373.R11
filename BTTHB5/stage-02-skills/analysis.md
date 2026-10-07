# Stage 02 — Tra cứu chính sách đúng phiên bản

Nguồn yêu cầu: https://pub.nndkhoa9.win/agentic-ai-engineering/d05-tool-use-skill-use/exercise-block-1.html

Stage 02 được thực hiện trên bản sao độc lập; project mẫu giữ nguyên. Stage 01 bổ sung nằm trong thư mục stage-01-files của gói Block 1.

## Thay đổi

- `tools/files.py`: thêm `list_files(path)` với JSON thành công/lỗi cùng quy ước tool cũ. Liệt kê mục trực tiếp, sắp xếp theo tên; mỗi mục có `name`, `path`, `type`. Tái sử dụng `_resolve` để kiểm tra đường dẫn, bao gồm symlink. Nếu một mục là symlink ra ngoài, trả lỗi cho toàn bộ lượt liệt kê, không đi theo mục đó.
- `tools/__init__.py`, `agent.py`: export và đăng ký tool mới. `config.py` cập nhật dòng mô tả tool hiển thị.
- `workspace/skills/refund-policy/SKILL.md` và `references/answer-template.md`: tìm tài liệu theo tên hiện có, chọn theo ngày mua, hỏi lại thông tin thiếu, trả lời có căn cứ. Có bản trong `fixtures/` để reset không mất skill.
- Hai chính sách trong `workspace/data/policies/` và bản tương ứng trong `fixtures/`.
- Không thêm tên file chính sách, nội dung chính sách hay đáp án vào system prompt hoặc tool. Không cấp Bash cho agent.

## Kiểm tra tool đã thực hiện

Bằng chứng gọi tool trực tiếp: `traces/tool-checks.jsonl`, mỗi dòng là kết quả JSON thật của tool; đây không phải trace cuộc trò chuyện với model.

| Dòng | Đường dẫn | Kết quả thực tế |
|---|---|---|
| 1 | `data/policies` | Thành công, liệt kê hai file theo tên |
| 2 | `data/weekly_notes.md` | `NOT_A_DIRECTORY` |
| 3 | `data/no-such-directory` | `DIRECTORY_NOT_FOUND` |
| 4 | `../outside` | `PATH_OUTSIDE_WORKSPACE` |
| 5 | `/tmp` | `PATH_OUTSIDE_WORKSPACE`, không truy cập đích |

`tests/test_list_files.py` kiểm tra cả thư mục rỗng, không duyệt đệ quy, đường dẫn rỗng, symlink thư mục ra ngoài, symlink mục con ra ngoài, symlink nội bộ và tìm/đọc tài liệu sau đổi tên. Dữ liệu ngoài workspace trong test chỉ là dữ liệu giả tạo trong thư mục tạm.

## Kết quả bộ kiểm thử

Đã chạy `.venv/bin/python -m pytest -q`: **56 passed in 3.45s** (kiểm tra lại lúc hoàn thiện giao diện ngày 07/10/2026), không test bị bỏ qua. Có test bảo mật đường dẫn, tìm tài liệu sau đổi tên và hồi quy bảo toàn metadata Gemini. Các test agent/UI gốc dùng mock; kết quả dưới đây được chạy riêng với model thật.

## Kiểm tra với model thật

Đã chạy model `gemini-3.8-flash` với cấu hình provider bên ngoài project. Không sao chép file cấu hình hoặc API key vào bài nộp. Đã kiểm tra bài nộp không chứa giá trị API key.

Cả 5 lượt có conversation_id khác nhau, chỉ một lượt chat mỗi conversation. Schema gửi model có read_file, write_file, list_files. Snapshot đầu chỉ có metadata skill; snapshot sau đọc skill có nội dung SKILL.md; snapshot tiếp sau đọc reference có nội dung reference. Các câu hỏi không nhắc skill, file hoặc thứ tự tool.

| Trường hợp | Kết quả thực tế | Kết quả kiểm tra |
|---|---|---|
| A | Chính sách trước tháng 10, 8 ngày, vượt 7 ngày; không đủ điều kiện | Đạt |
| B | Chính sách từ tháng 10, 10 ngày; đủ điều kiện, không thu phí | Đạt |
| A sau đổi tên | 8 ngày, không đủ; căn cứ document-alpha.md | Đạt |
| B sau đổi tên | 10 ngày, đủ, miễn phí; căn cứ document-beta.md | Đạt |
| Thiếu kích hoạt | Hỏi sản phẩm đã kích hoạt hay chưa, chưa kết luận điều kiện/phí | Đạt |

`traces/case-results.json` lưu nguyên câu trả lời model và ánh xạ tới trace. JSONL dùng observer có sẵn, ghi tool result và request snapshot; event model_response chỉ ghi thống kê, nên nội dung câu trả lời cuối đối chiếu ở case-results.json.

## Vị trí bằng chứng

Số dòng dưới đây cũng là sequence của event. Đường dẫn file dưới `traces/`.

- **A** — `20261007-101915_2d0926e8_turn01_4cb71c7b.jsonl`: Dòng 5: skill; 10: reference; 11: list_files; 16: đọc chính sách cũ, 17: chính sách mới; 18: snapshot đủ căn cứ.
- **B** — `20261007-101934_bf2be6bd_turn01_559b7b68.jsonl`: Dòng 5: skill; 10: reference; 11: list_files; 16: chính sách mới, 17: chính sách cũ; 18: snapshot đủ căn cứ.
- **A-renamed** — `20261007-101950_2c82f412_turn01_1c1c0728.jsonl`: Dòng 5: skill; 9: reference; 13: list_files tìm tên mới; 17: document-alpha.md, 21: document-beta.md; 22: snapshot đủ căn cứ.
- **B-renamed** — `20261007-102012_47b71a4b_turn01_c4f3702f.jsonl`: Dòng 5: skill; 10: reference; 11: list_files tìm tên mới; 16: document-beta.md, 17: document-alpha.md; 18: snapshot đủ căn cứ.
- **missing-activation** — `20261007-102034_db9f4feb_turn01_0b4c48c9.jsonl`: Dòng 5: skill; 9: reference; 10: snapshot trước câu hỏi bổ sung. Không đọc chính sách hay đưa kết luận khi chưa có kích hoạt.

Mỗi trace: dòng 2 là snapshot đầu (catalog + schema tools), dòng 6 là snapshot sau khi đọc skill. Sau thử đổi tên, hai file trong workspace được khôi phục tên gốc; trace giữ nguyên tên thực tế tại thời điểm kiểm tra.

## Tương thích Gemini và chạy lại

Lần thử đầu API trả HTTP 400 do thiếu thought_signature: ChatOpenAI bỏ metadata extra_content của tool call khi chuyển message. `scripts/gemini_compat.py` giữ nguyên metadata do provider trả về và gửi lại ở request sau, không tạo chữ ký giả và không sửa câu trả lời/tool result. Áp dụng trong `agent.build_model` khi dùng endpoint Gemini, dùng chung cho giao diện Streamlit và script kiểm tra; không sửa logic chọn chính sách hoặc system prompt. Test hồi quy kiểm tra chữ ký qua vòng history và phản hồi cuối có tool_calls=null.

Căn cứ tích hợp: [OpenAI compatibility của Gemini](https://ai.google.dev/gemini-api/docs/openai), [Thinking guide](https://ai.google.dev/gemini-api/docs/thinking).

Chạy từ thư mục stage này:

```bash
uv sync --locked
uv run python scripts/run_cases.py --env-file /duong/dan/cau-hinh.env.local
```

Script chấp nhận GEMINI_API_KEY/GEMINI_MODEL hoặc OPENAI_API_KEY/MODEL_NAME/OPENAI_BASE_URL, chỉ nạp các trường cấu hình model cần thiết. Chạy cả 5 cuộc trò chuyện mới, tự đổi tên hai tài liệu cho hai lượt kiểm tra rồi khôi phục trong finally. Không chứa đáp án định sẵn. Cần đối chiếu trace và câu trả lời sau mỗi lần chạy vì kết quả model có thể thay đổi.

## Câu hỏi cuối bài

Tool cung cấp khả năng thao tác: `list_files` phát hiện tên và đường dẫn hiện có, `read_file` đưa nội dung tài liệu vào lịch sử. Skill cung cấp quy trình chọn và áp dụng: chọn phạm vi theo ngày mua, kiểm tra thông tin thiếu, tính ngày lịch, xét kích hoạt và dẫn căn cứ.

Sửa prompt không tạo ra khả năng liệt kê thư mục khi agent chưa có tool tìm file. Gợi ý tên file cố định có thể giúp đọc ở một trạng thái cụ thể nhưng thất bại khi file đổi tên. Cần tool để quan sát workspace và skill để hướng dẫn dùng thông tin đó đúng cách.

## Kiểm chứng giao diện Streamlit (07/10/2026, khoảng 18:42–18:47 giờ Việt Nam)

Giữ giao diện `app.py` từ project mẫu. Chat gửi từng yêu cầu đến model thật; không đọc đáp án từ `case-results.json`. `scripts/run_ui.py --env-file` hỗ trợ chọn file cấu hình bên ngoài, chỉ lấy thông số model. `agent.build_model` chọn adapter bảo toàn thought_signature cho endpoint Gemini. Bộ kiểm thử: 56 passed; browser console không có error/warn trong phiên kiểm tra.

Mỗi trường hợp A, B, A-renamed, B-renamed và thiếu kích hoạt đều bắt đầu bằng nút Cuộc trò chuyện mới. Kết quả A là không đủ/8 ngày; B là đủ/10 ngày/không phí; đổi tên không làm thay đổi kết luận. Thiếu kích hoạt: hỏi lại, chưa kết luận; khi trả lời bổ sung trong cùng conversation, agent trả đủ/10 ngày/không phí. Đã khôi phục hai tên file gốc sau kiểm tra.

`traces/ui-results.json` chứa câu trả lời trích từ DOM cho B, A-renamed, B-renamed và thiếu thông tin; mục A ghi rõ là tóm tắt quan sát. Các JSONL UI mới là trace thực thi thật. Trace dùng observer gốc nên `model_response` ghi thống kê; câu trả lời cuối đối chiếu với ui-results.json. Mốc giờ trong timestamp event dùng UTC, còn tên file trace do runtime đặt theo giờ máy.

| Trường hợp UI | Trace trong traces/ | Bằng chứng theo số dòng |
|---|---|---|
| A | `20261007-184204_aa4522a2_turn01_2e72a1e4.jsonl` | 5: read_file `skills/refund-policy/SKILL.md`; 10: read_file `skills/refund-policy/references/answer-template.md`; 11: list_files `data/policies`; 16: read_file `data/policies/policy-from-oct.md`; 17: read_file `data/policies/policy-before-oct.md`; 20: hoàn tất |
| B | `20261007-184312_3631b9cf_turn01_0cd35766.jsonl` | 5: read_file `skills/refund-policy/SKILL.md`; 10: read_file `skills/refund-policy/references/answer-template.md`; 11: list_files `data/policies`; 16: read_file `data/policies/policy-from-oct.md`; 17: read_file `data/policies/policy-before-oct.md`; 20: hoàn tất |
| A-renamed | `20261007-184414_d610d923_turn01_661860cf.jsonl` | 5: read_file `skills/refund-policy/SKILL.md`; 10: read_file `skills/refund-policy/references/answer-template.md`; 11: list_files `data/policies`; 16: read_file `data/policies/document-alpha.md`; 17: read_file `data/policies/document-beta.md`; 20: hoàn tất |
| B-renamed | `20261007-184516_9eb7c33a_turn01_8684d301.jsonl` | 5: read_file `skills/refund-policy/SKILL.md`; 10: read_file `skills/refund-policy/references/answer-template.md`; 11: list_files `data/policies`; 16: read_file `data/policies/document-alpha.md`; 17: read_file `data/policies/document-beta.md`; 20: hoàn tất |
| missing-activation | `20261007-184604_91d11d5a_turn01_58547c22.jsonl` | 5: read_file `skills/refund-policy/SKILL.md`; 9: read_file `skills/refund-policy/references/answer-template.md`; 12: hoàn tất |
| activation-follow-up | `20261007-184647_91d11d5a_turn02_6ba83b20.jsonl` | 5: list_files `data/policies`; 9: read_file `data/policies/policy-from-oct.md`; 13: read_file `data/policies/policy-before-oct.md`; 16: hoàn tất |

Snapshot đầu của mỗi conversation là dòng 2: chỉ catalog, schema và câu hỏi. Dòng 6 ở năm trace lượt 1 đã có nội dung skill trong tool result. Gói Block 1 hiện có thêm stage-01-files đáp ứng phần đăng ký list_files ở stage 01.

## Trace theo case-results.json hiện tại

| Case | Trace | Tool result theo dòng JSONL |
|---|---|---|
| A | `20261007-102823_0678646c_turn01_29e5c9ac.jsonl` | 5: read_file; 10: read_file; 11: list_files; 16: read_file; 17: read_file |
| B | `20261007-102841_0fa0d261_turn01_971bff0d.jsonl` | 5: read_file; 10: list_files; 11: read_file; 16: read_file; 17: read_file |
| A-renamed | `20261007-102854_8786e384_turn01_96bd2190.jsonl` | 5: read_file; 10: list_files; 11: read_file; 16: read_file; 17: read_file |
| B-renamed | `20261007-102912_17506577_turn01_b2fd2068.jsonl` | 5: read_file; 10: read_file; 11: list_files; 16: read_file; 17: read_file |
| missing-activation | `20261007-102928_1bae65a7_turn01_11f68c19.jsonl` | 5: read_file; 9: read_file |
