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
