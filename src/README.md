# Code Day 7

## Bước 2 — dữ liệu và benchmark

| File | Công dụng | Lệnh |
|---|---|---|
| `adapt_day6.py` | Chuyển corpus/benchmark Day 6 sang schema Day 7 | `python src/adapt_day6.py` |
| `validate_benchmark.py` | Kiểm tra ràng buộc benchmark + hash đóng băng | `python src/validate_benchmark.py [--freeze]` |
| `check_absence.py` | Bằng chứng vắng mặt (lexical + dense + keyword) | `python src/check_absence.py` |

## Bước 3 — retrieval

| File | Công dụng |
|---|---|
| `build_index.py` | Dựng index 111 unit vào `artifacts/day7/chroma` (collection `day7_units_384`) |
| `run_retrieval.py` | Chạy dense / dense_day6 / bm25 / hybrid, ghi summary + traces |
| `retrieval/bm25.py` | BM25Okapi thuần Python |
| `retrieval/dense.py` | Chroma + fastembed `BAAI/bge-small-en-v1.5` (384 chiều) |
| `retrieval/dense_day6.py` | Ablation: dense trên collection Day 6 rồi gộp về unit |
| `retrieval/hybrid.py` | RRF (k=60) giữa dense và BM25 |
| `retrieval/context.py` | Pack context theo budget ký tự, dedup |
| `retrieval/evaluate.py` | Hit@1 / Evidence Hit@3 / Context Evidence Rate |

```powershell
python src/build_index.py
python src/run_retrieval.py --methods dense,dense_day6,bm25,hybrid --split dev
```

Dev (15 câu): dense 3/15 · dense_day6 6/15 · bm25 10/15 · hybrid 8/15 (Hit@1); Evidence Hit@3 lần lượt 10/15, 11/15, 11/15, **12/15**. Chi tiết: [docs/RETRIEVAL.md](../docs/RETRIEVAL.md).

## Bước 4 — agent

| File | Công dụng |
|---|---|
| `run_agent.py` | Chạy agent trên dev/test, ghi `traces.json`, `cases.json`, `run_meta.json` |
| `agent/providers.py` | Adapter OpenAI-compatible và Ollama (HTTP thật, không mock) |
| `agent/controller.py` | Prompt, parse JSON, validate action |
| `agent/tools.py` | Ba tool retrieval; filter do harness cấp |
| `agent/loop.py` | Vòng lặp, citation, abstention, trace |
| `agent/scripted.py` | Controller kịch bản — chỉ để test đường ống |

```powershell
$env:DAY7_LLM_PROVIDER="openai"; $env:DAY7_LLM_MODEL="gpt-4o-mini"; $env:DAY7_LLM_API_KEY="<key>"
python src/run_agent.py --split dev --out artifacts/day7/results/agent-dev
```

Thiết kế và trạng thái: [docs/AGENT.md](../docs/AGENT.md).

## Kiểm thử

```powershell
python -m unittest discover -s tests     # 34/35 pass; 1 lỗi do sandbox chặn chmod khi dọn tempfile
```

`tests/test_day7_retrieval.py` (13 test) và `tests/test_day7_agent.py` (7 test) phủ BM25, RRF, context packing, định nghĩa hit, parse action, citation sai và lỗi provider.

## Cấu trúc dữ liệu

```
data/day6/                 chunks.json, questions.json, abstain.json, abstain_checks.json,
                           manifest.json, benchmark_manifest.json, raw/
artifacts/day7/
  chroma/                  index dense 111 unit (gitignore)
  index_manifest.json      model, số chiều, thời gian, chi phí
  results/dev-*/           summary.json, traces.json, run_config.json
```
## Bước 5–6 — thử cấu hình, chốt và chạy test

```powershell
# so sánh cấu hình trên dev (mỗi lệnh một thư mục riêng)
python src/run_agent.py --split dev  --include-abstain --max-searches 3 --context-budget 6000 --out artifacts/day7/results/agent-dev-c2

# sinh bảng chấm tay rồi chấm
python src/review_sheet.py --run artifacts/day7/results/agent-dev-c2 --out artifacts/day7/reviews/dev-c2.md

# tổng hợp nhãn đã chấm
python starter/agent_metrics.py --cases artifacts/day7/results/agent-dev-c2/cases.json `
  --traces artifacts/day7/results/agent-dev-c2/traces.json `
  --reviews artifacts/day7/reviews/c2-reviews.json --split dev `
  --output artifacts/day7/results/agent-dev-c2/agent_metrics.json

# sau khi chốt mới chạy test
python src/run_agent.py --split test --include-abstain --max-searches 3 --context-budget 6000 --out artifacts/day7/results/agent-test-c2
```

Tiêu chí chọn ghi trước ở [docs/STEP5_PROTOCOL.md](../docs/STEP5_PROTOCOL.md); kết quả dev ở [docs/STEP5_RESULTS.md](../docs/STEP5_RESULTS.md); kết quả test ở [docs/STEP6_RESULTS.md](../docs/STEP6_RESULTS.md).
