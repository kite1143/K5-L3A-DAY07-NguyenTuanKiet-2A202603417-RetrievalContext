# Bước 5 — Giao thức chốt cấu hình (ghi trước khi chạy)

Ghi ngày 2026-11-14, **trước** khi chạy hai cấu hình cải thiện. Mọi thay đổi tiêu chí sau đây phải ghi rõ lý do và thời điểm.

## 1. Cấu hình so sánh

| Mã | Retrieval | Agent |
|---|---|---|
| **B0** | `hybrid` = RRF(dense unit, BM25), k=60, depth=20 | max_searches=2, max_steps=5, top_k=5, budget=4.000, temperature=0 |
| **C1** | `hybrid_day6` = RRF(dense Day 6 paragraph → unit, BM25) | như B0 |
| **C2** | `hybrid` (như B0) | max_searches=3, budget=6.000, còn lại như B0 |

Giả thuyết:

- **C1** — dense trên unit bị cắt ở 512 token nên phần lớn văn bản không được embedding; chuyển nhánh dense sang paragraph Day 6 rồi gộp về unit sẽ tăng Evidence Hit@3 và Context Evidence Rate mà không đổi model, không đổi corpus.
- **C2** — budget 4.000 chỉ chứa 2 unit và 2 lượt search làm q17 chạm giới hạn; nới lên 6.000 và 3 lượt sẽ giảm từ chối nhầm, đổi lại token/chi phí tăng.

## 2. Tiêu chí chọn, theo thứ tự ưu tiên

1. **Chất lượng câu trả lời** (grounded answer 0/1/2, chấm tay trên dev): điểm trung bình /2 phải cao hơn B0; nếu bằng nhau thì xét tỷ lệ câu đạt 2.
2. **Citation hợp lệ** (số citation trong context *và* hỗ trợ câu trả lời / tổng citation, chấm tay).
3. **Không từ chối nhầm** câu có đáp án (thấp hơn B0) và **từ chối đúng** câu thiếu evidence (không giảm so với 2/2).
4. **Retrieval**: Evidence Hit@3 và Context Evidence Rate trên dev.
5. **Chi phí/thời gian**: token và giây mỗi câu; chỉ dùng để phá thế hoà ở mục 1–4.

Quy tắc chốt: chọn cấu hình thoả mục 1 **và** không giảm mục 3. Nếu nhiều cấu hình cùng thoả, chọn cái tốt hơn ở mục 2, rồi 4, rồi 5. Không chọn cấu hình chỉ vì Hit@1 cao hơn nếu câu trả lời tệ hơn.

## 3. Cách chấm (thang của BENCHMARK.md)

- Grounded answer: 0 = sai hoặc thiếu evidence; 1 = đúng một phần; 2 = đúng và đủ. Từ chối câu có đáp án = 0.
- Citation hợp lệ: đọc đoạn được cite, xác nhận có hỗ trợ điều kiện trong câu trả lời (không chỉ kiểm ID).
- Abstention: đúng nếu agent từ chối câu thiếu evidence và lý do khớp; từ chối nhầm nếu câu có đáp án mà bị từ chối.

## 4. Giới hạn đã biết trước khi chấm

- Dev chỉ 15 câu có đáp án; chênh 1 câu = 6,7 điểm phần trăm, nên chỉ kết luận khi khác biệt ≥2 câu.
- Chấm do người làm bài thực hiện, không dùng LLM judge.
- Test **không** được chạy cho tới khi mục 5 hoàn tất và cấu hình được ghi vào mục 6 (dưới đây).

## 5. Kết quả chốt

Đã chốt **C2**: `hybrid` unit, `max_searches=3`, `context_budget=6000`, `top_k=5`, temperature 0. Lý do và số liệu: [STEP5_RESULTS.md](STEP5_RESULTS.md).
