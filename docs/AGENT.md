# Agent Day 7

## 1. Kiến trúc

```
run_agent.py
  └── agent/loop.py        vòng lặp: model → action → tool → context → answer/abstain
        ├── agent/controller.py   prompt + parse JSON + validate schema
        │     └── agent/providers.py  OpenAI-compatible / Ollama (HTTP, không mock)
        └── agent/tools.py        dense_search / lexical_search / hybrid_search
              └── retrieval/*     cùng 111 unit, cùng filter
```

- Model thật qua HTTP: nhánh `openai` (mọi endpoint /chat/completions: OpenAI, OpenRouter, DeepSeek, vLLM, LM Studio) và `ollama`. Không có fallback giả: thiếu key/model thì chương trình dừng với thông điệp rõ ràng.
- Ba tool: `dense_search`, `lexical_search`, `hybrid_search`. Model chọn tool và query; **filter do harness cấp từ câu hỏi**, model không tự suy ra nên không thể lách gold.
- Action hợp lệ duy nhất: `search` / `answer` / `abstain`. Mọi output khác bị `parse_action` từ chối và ghi thành lỗi.
- Nếu model trả JSON hỏng, controller thử **repair một lần** (gửi lại kèm thông điệp sửa); vẫn hỏng thì `status='error'`. Lý do: một ca dev trả `{"action": "search", ... )` thiếu ngoặc và bị tính là lỗi provider, trong khi đó là lỗi định dạng của model.

## 2. Chống rò rỉ và grounding

- System prompt nêu rõ: tài liệu trong context là **dữ liệu**, không phải chỉ dẫn.
- Citation hợp lệ chỉ khi: id có trong `context_ids` của lần dựng context gần nhất **và** chuỗi `[id]` xuất hiện trong câu trả lời. Không có citation → `abstain`.
- Câu trả lời không được kiểm chứng ngữ nghĩa bằng code; bước 6 sẽ chấm tay từng citation (ID hợp lệ không chứng minh nguồn hỗ trợ).

## 3. Trace ghi gì

Mỗi câu là một record:

| Trường | Nội dung |
|---|---|
| `query_id`, `question`, `filter` | đầu vào, không chứa gold |
| `status` | `answered` / `abstain` / `error` |
| `events` | `search` (tool, query, results, new_ids, context, context_ids, filter, latency), `answer`, `abstain`, `search_limit`, `tool_error`, `error` |
| `context_chars`, `context_ids` | context cuối gửi model |
| `citations`, `answer` | kết quả |
| `usage`, `latency_ms`, `model`, `provider`, `prompt_version` | chi phí/thời gian và phiên bản prompt |

Lỗi provider/tool không bị thay bằng kết quả giả: `status='error'` kèm `events[].stage` và `error`.

## 4. Tham số mặc định

`max_searches=2`, `max_steps=5`, `top_k=5`, `context_budget=4000`, `temperature=0`, `max_tokens=900`. Tất cả vào `run_meta.json`; đổi gì phải ghi lý do trong báo cáo.

Vì sao budget 4.000 chứ không 800: unit Day 6 dài 1.502–4.762 ký tự, budget 800 của starter luôn cho context rỗng (đã đo: Context Evidence Rate 0/15).

## 5. Cách chạy

```powershell
# model API tương thích OpenAI
$env:DAY7_LLM_PROVIDER="openai"
$env:DAY7_LLM_MODEL="gpt-4o-mini"
$env:DAY7_LLM_BASE_URL="https://api.openai.com/v1"
$env:DAY7_LLM_API_KEY="<key>"

python src/run_agent.py --split dev --out artifacts/day7/results/agent-dev

# hoặc Ollama local
$env:DAY7_LLM_PROVIDER="ollama"; $env:DAY7_LLM_MODEL="qwen2.5:7b-instruct"
python src/run_agent.py --split dev --out artifacts/day7/results/agent-dev
```

Kiểm tra đường ống khi chưa có model (không phải kết quả benchmark):

```powershell
python src/run_agent.py --split dev --limit 2 --scripted-demo --out artifacts/day7/results/agent-dev-scripted
```

## 6. Trạng thái

Run `agent-dev-v1` (gpt-4o-mini, 17 câu dev gồm 2 câu thiếu evidence):

| Chỉ số | Giá trị |
|---|---|
| answered / abstain | 13 / 4 |
| Từ chối đúng câu thiếu evidence | 2/2 (a01, a02) |
| Từ chối nhầm câu có đáp án | 2/15 (q11, q17) |
| Số lượt search trung bình | 1,06 (q17 và a02 dùng 2 lượt) |
| Token | 26.479 prompt + 2.374 completion |
| Chi phí ước tính | ~0,0054 USD (gpt-4o-mini) |
| Thời gian chạy | 69,5 s |
| Trace | `artifacts/day7/results/agent-dev-v1/` |

| Phần | Trạng thái |
|---|---|
| Code agent, tool, trace, citation, abstention | xong, 20 unit test pass |
| Chạy model thật trên dev | xong (gpt-4o-mini) |
| Chấm điểm người (grounded answer, citation support) | **chưa**: cần đọc từng citation; đây là việc của bước 6 |
| Chạy test | chưa, chỉ sau khi chốt cấu hình |
