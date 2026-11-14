# Retrieval Day 7

## 1. Index và đơn vị văn bản

Tất cả phương pháp chạy trên **cùng 111 unit** của Day 6 (data/day6/chunks.json) để so sánh công bằng: cùng đơn vị văn bản, cùng câu hỏi, cùng bộ nhãn dev.

| Thành phần | Giá trị |
|---|---|
| Dense index Day 7 | `artifacts/day7/chroma`, collection `day7_units_384`, 111 vector |
| Embedding | fastembed `BAAI/bge-small-en-v1.5`, 384 chiều, L2-normalised, cosine |
| Thời gian dựng index | 27,99 s (CPU, local, 0 USD) — `artifacts/day7/index_manifest.json` |
| Lexical index | BM25Okapi (k1=1,5; b=0,75) trên chính 111 text đó |
| Filter | chỉ metadata `book` (1–3), cấp từ câu hỏi trước khi truy xuất |
| Ngưỡng so sánh | top-3 cho Hit@1 / Evidence Hit@3; context lấy top-5, budget 4.000 ký tự |

Vì sao không dùng thẳng collection Day 6: chunk Day 6 là paragraph (184 chunk, ≤1.736 ký tự) còn hợp đồng dữ liệu Day 7 là unit (111 chunk). Dùng lẫn hai granularity sẽ làm sai so sánh. Collection Day 6 vẫn được dùng ở `dense_day6` như một **ablation về granularity** (bên dưới).

## 2. Bốn phương pháp

| Tên | Cách hoạt động |
|---|---|
| `dense` | Embed câu hỏi bằng đúng model Day 6, cosine trên 111 unit |
| `dense_day6` | Truy vấn collection Day 6 `republic_B_384` (paragraph), gộp về unit bằng cosine lớn nhất trong các paragraph của unit |
| `bm25` | BM25Okapi, tokenize NFC + casefold + stopword tiếng Anh |
| `hybrid` | RRF (k=60, depth=20) giữa `dense` và `bm25` — chỉ dùng thứ hạng nên không phải chuẩn hoá hai thang điểm khác nhau |

## 3. Kết quả dev (15 câu có đáp án)

| Phương pháp | Hit@1 | Evidence Hit@3 | Context Evidence Rate | avg context | median ms |
|---|---:|---:|---:|---:|---:|
| dense (unit) | 3/15 — 20,0% | 10/15 — 66,7% | 7/15 — 46,7% | 3.284 | 14,8 |
| dense_day6 (paragraph → unit) | 6/15 — 40,0% | 11/15 — 73,3% | 9/15 — 60,0% | 3.222 | 16,5 |
| bm25 | **10/15 — 66,7%** | 11/15 — 73,3% | **10/15 — 66,7%** | 3.277 | **1,6** |
| hybrid RRF | 8/15 — 53,3% | **12/15 — 80,0%** | 9/15 — 60,0% | 3.427 | 32,1 |
| hybrid_day6 (RRF + nhánh dense paragraph) | 9/15 — 60,0% | **12/15 — 80,0%** | 8/15 — 53,3% | 3.294 | 37,3 |

Số liệu thô: `artifacts/day7/results/dev-*/{summary,traces}.json`; bảng gộp: `artifacts/day7/results/dev-retrieval-comparison.json`.

Riêng nhóm có filter (`book`, 3 câu dev): dense 1/3, dense_day6 2/3, bm25 2/3, hybrid 1/3 theo Hit@1.

## 4. Đọc kết quả

- **Dense unit yếu nhất và đây là lỗi thiết kế, không phải ngẫu nhiên.** `bge-small-en-v1.5` chỉ nhận 512 token (~350–400 từ), trong khi unit Day 6 dài 1.502–4.762 ký tự. Phần lớn văn bản không được đưa vào vector.
- **`dense_day6` xác nhận giả thuyết đó:** cùng model, cùng store, chỉ đổi đơn vị truy vấn sang paragraph Day 6 rồi gộp về unit → Hit@1 tăng 3/15 → 6/15, Hit@3 10/15 → 11/15. Đây là ứng viên chính cho cấu hình cải thiện ở bước 5.
- **BM25 mạnh trên corpus này** vì câu hỏi Day 6 dùng nhiều từ khoá trùng với bản dịch Jowett ("guardians", "harmony", "imitations", "weapons"). Cần cảnh báo trong báo cáo: đây là benchmark thiên về từ vựng.
- **Hybrid có Hit@3 cao nhất (12/15)** nhưng Hit@1 thấp hơn BM25 vì RRF đẩy một số kết quả dense lên đầu. Đổi trọng số/RRF k hoặc dùng dense_day6 làm nhánh dense là hai hướng cải thiện ở bước 5.
- **Context Evidence Rate thấp hơn Hit@3 ở mọi phương pháp** vì budget 4.000 ký tự chỉ chứa được 2–3 unit, thứ tự ưu tiên theo hạng chứ không theo "unit nào chứa nhiều evidence". Đây là chỗ cải thiện rõ ràng của bước 5 (chọn context theo cửa sổ, không chỉ theo hạng).

## 5. Xử lý lỗi

| Tình huống | Hành vi | Kiểm bằng |
|---|---|---|
| filter có khoá lạ (ví dụ `page`, `unit_id`) | `ValueError` trước khi truy vấn, không âm thầm bỏ qua | `tests/test_day7_retrieval.py::ErrorHandlingTests::test_filter_validation_rejects_unknown_keys` |
| `top_k <= 0`, `k1 <= 0`, `b` ngoài [0,1] | `ValueError` khi khởi tạo hoặc khi search | `test_bm25_rejects_invalid_arguments` |
| corpus rỗng | `ValueError`, không trả ranking giả | cùng test trên |
| `budget <= 0` hoặc `block_cap <= 0` | `ValueError` | `test_pack_context_rejects_invalid_budget` |
| sai số chiều embedding | `ValueError` nêu số chiều mong đợi và nhận được | kiểm trong `Embedder` khi dựng index |
| retriever trả trùng ID hoặc quá `top_k` | `evaluate` dừng với lỗi, không ghi metric sai | `src/retrieval/evaluate.py` |
| vector store/model không tải được | lỗi lan ra CLI, dừng run; agent ghi `status='error'` | `tests/test_day7_agent.py::ToolErrorTests::test_tool_failure_becomes_error_status` |

Không có nhánh nào thay lỗi bằng kết quả giả.

## 6. Lệnh chạy

```powershell
python src/build_index.py                                     # dựng index unit (1 lần)
python src/run_retrieval.py --methods dense,dense_day6,bm25,hybrid --split dev
```

Đổi tham số so sánh phải ghi lại: `--top-k`, `--context-depth`, `--context-budget` đều vào `run_config.json` của từng run.
