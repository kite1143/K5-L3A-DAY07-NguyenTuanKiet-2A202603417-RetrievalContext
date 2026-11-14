# Bước 6 — Kết quả trên test

Chạy ngày 2026-11-14, **sau khi** đã chốt C2 ở bước 5 ([STEP5_RESULTS.md](STEP5_RESULTS.md)). Test gồm 5 câu có đáp án (q04, q07, q10, q14, q18) và 2 câu thiếu evidence (a03, a04). Hash benchmark không đổi: `src/validate_benchmark.py` trả `errors=0`.

## 1. Agent

| Chỉ số | Baseline B0 | **Cấu hình chọn C2** |
|---|---:|---:|
| Grounded answer 0/1/2 | 2/1/2 | **1/1/3** |
| Điểm trung bình /2 | 1,00 | **1,40** |
| Citation hợp lệ | 1/6 (16,7%) | **3/6 (50,0%)** |
| Câu trả lời có citation | 3/3 | 4/4 |
| Từ chối đúng câu thiếu evidence | 2/2 | 2/2 |
| Từ chối nhầm câu có đáp án | 2/5 | **1/5** |
| Tool use | 7/7 | 7/7 |
| Token (in + out) | 10.155 + 881 | 14.338 + 966 |
| Chi phí | 0,0021 USD | 0,0027 USD |
| Thời gian | 28,7 s | 30,3 s |

Nhãn chấm tay: `artifacts/day7/reviews/test-c2.md`, `test-c2-reviews.json`; baseline: `test-b0.md`, `test-b0-reviews.json`.

## 2. Chấm từng câu

| ID | Loại | Context 0/1/2 (B0 → C2) | Grounded B0 | Grounded C2 | Ghi chú |
|---|---|---|---:|---:|---|
| q04 | paraphrase, craft analogy | 0 → 0 | 2 | 2 | Trả lời đúng ý; gold `rep-b1-u022` không bao giờ vào top-5 |
| q07 | direct, ring of Gyges | 0 → 0 | **0** (từ chối) | **1** | Gold `rep-b2-u003` dài 4.762 ký tự, bị loại khỏi context; C2 trả lời đúng nhờ kiến thức sẵn có nhưng citation không hỗ trợ |
| q10 | direct, nguồn gốc chiến tranh | 2 → 2 | 2 | 2 | Gold vào context, trả lời và citation đúng |
| q14 | condition/exception, quá nhiều music | 0 → 0 | 0 (từ chối) | **0** (từ chối) | Gold `rep-b3-u035` xếp thứ 4, budget đầy trước khi tới |
| q18 | condition/exception, ngoại lệ kim loại | 0 → **2** | 1 | **2** | C2 lấy được gold `rep-b3-u041` và trả lời đủ ý |
| a03 | thiếu evidence | — | đúng | đúng | Từ chối kèm lý do khớp |
| a04 | thiếu evidence | — | đúng | đúng | Từ chối kèm lý do khớp |

Context grade: 0 = không có evidence trong context; 1 = có nhưng thiếu nguồn/điều kiện; 2 = đủ evidence và nguồn. Không có câu nào mức 1 vì context chứa nguyên văn unit.

## 3. Nguyên nhân lỗi test

1. **q07 — gold unit bị loại vì độ dài.** `rep-b2-u003` dài 4.762 ký tự; sau unit đầu tiên (1.618) chỉ còn ~4.300 nên block bị bỏ, các unit ngắn hơn chen vào. Model trả lời đúng nội dung (invisible) nhưng **không có evidence trong context** → chấm 1, citation sai. Đây là rủi ro grounding thật, không phải lỗi định dạng.
2. **q14 — gold xếp thứ 4.** Truy vấn "guardian indulge excessively music Socrates" trả về `rep-b3-u037, u039, u024, u035 (gold), u036`; 3 unit đầu chiếm hết 6.000 ký tự. C2 từ chối đúng vì context thiếu, nhưng đây là **từ chối nhầm** do retrieval xếp hạng, không do thiếu tri thức.
3. **q04 — gold ngoài top-5.** Cả hai cấu hình trả lời đúng nhờ đoạn shepherd/craft lân cận, nhưng citation trỏ unit không chứa luận điểm → citation validity thấp (1/6 và 3/6).

## 4. So dev và test

| | Dev (17 câu) | Test (7 câu) |
|---|---|---|
| C2 grounded mean | 1,73 | 1,40 |
| C2 từ chối nhầm | 1/15 | 1/5 |
| C2 citation hợp lệ | 15/19 (79%) | 3/6 (50%) |

Test khó hơn dev ở hai điểm: (a) 2/5 câu test là loại condition/exception, dạng cần đúng một đoạn cụ thể; (b) test có q07 với gold unit dài nhất corpus. Xu hướng giữ nguyên: C2 tốt hơn baseline ở cả dev và test, nhưng **grounding vẫn là điểm yếu chính** — không phải chất lượng văn bản trả lời.

## 5. Kết luận cho báo cáo

- Cấu hình C2 tốt hơn baseline trên test ở cả 4 thước đo chất lượng (grounded mean, citation, từ chối nhầm, context grade) với chi phí tăng 33% (0,0021 → 0,0027 USD cho 7 câu).
- Không được kết luận "agent đáng tin": 3/5 câu có đáp án vẫn có context grade 0, và 3/6 citation không hỗ trợ. Nguyên nhân chính là chính sách chọn context theo budget ký tự cứng, không ưu tiên unit chứa evidence dù unit đó dài.
- Hướng cải thiện (chưa làm, cần benchmark v2 nếu muốn dùng test để tinh chỉnh): (1) chấm điểm từng câu đoạn thay vì cả unit để chọn context; (2) rerank cắt bớt unit dài; (3) xử lý riêng unit > 4.000 ký tự bằng cửa sổ trượt.
