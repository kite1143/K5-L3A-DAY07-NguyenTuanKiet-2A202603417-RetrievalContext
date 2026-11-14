# Kết quả bước 3

| Thư mục | Nội dung |
|---|---|
| `dev-dense/` | Dense trên 111 unit |
| `dev-dense_day6/` | Dense trên collection Day 6 rồi gộp về unit (ablation granularity) |
| `dev-bm25/` | BM25Okapi |
| `dev-hybrid/` | RRF(dense, bm25), k=60, depth=20 |
| `dev-retrieval-comparison.json` | Bảng gộp 4 phương pháp |
| `agent-dev-v1/` | Agent thật (gpt-4o-mini) trên 17 câu dev: 13 answered, 4 abstain |
| `smoke-1/` | Chạy thử 1 câu để kiểm tra key/model |
| `agent-dev-scripted/` | **Chỉ kiểm tra đường ống** (`benchmark_result=false`), không dùng trong báo cáo |

Mỗi thư mục có `summary.json`, `traces.json` và `run_config.json` (tham số, model, budget, filter policy).

Bảng dev 15 câu:

| Phương pháp | Hit@1 | Evidence Hit@3 | Context Ev. Rate | median ms |
|---|---:|---:|---:|---:|
| dense | 3/15 | 10/15 | 7/15 | 14,8 |
| dense_day6 | 6/15 | 11/15 | 9/15 | 16,5 |
| bm25 | 10/15 | 11/15 | 10/15 | 1,6 |
| hybrid | 8/15 | 12/15 | 9/15 | 32,1 |

Chưa chạy test: test chỉ chạy sau khi chốt cấu hình trên dev.
## Bước 5 — bốn cấu hình agent trên dev

| Thư mục | Cấu hình | Grounded TB | Từ chối nhầm | Token | Chi phí |
|---|---|---:|---:|---|---:|
| `agent-dev-b0/` | hybrid unit, 2 lượt, budget 4.000 | 1,40 | 4/15 | 28.889 | 0,0054 USD |
| `agent-dev-c1/` | hybrid_day6, 2 lượt, budget 4.000 | 1,47 | 3/15 | 31.309 | 0,0057 USD |
| `agent-dev-c2/` | **hybrid unit, 3 lượt, budget 6.000 (đã chọn)** | **1,73** | **1/15** | 42.936 | 0,0077 USD |
| `agent-dev-c3/` | như C2 + block cap 1.400 | 1,53 | 2/15 | 34.818 | 0,0064 USD |

Mỗi thư mục có `traces.json`, `cases.json`, `run_meta.json`, `agent_metrics.json`. Nhãn chấm tay ở `artifacts/day7/reviews/` (`dev-<mã>.md` là bảng chấm, `<mã>-reviews.json` là nhãn dùng cho agent_metrics).
## Bước 6 — test (7 câu, đã đóng băng)

| Thư mục | Cấu hình | Grounded TB | Citation | Từ chối nhầm |
|---|---|---:|---:|---:|
| `agent-test-b0/` | baseline: hybrid, 2 lượt, budget 4.000 | 1,00 | 1/6 | 2/5 |
| `agent-test-c2/` | **chọn**: hybrid, 3 lượt, budget 6.000 | **1,40** | 3/6 | 1/5 |

Nhãn: `artifacts/day7/reviews/test-b0*.json`, `test-c2*.json`; bảng chấm tay: `test-b0.md`, `test-c2.md`.
