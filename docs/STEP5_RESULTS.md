# Bước 5 — Kết quả và cấu hình đã chốt

Chạy ngày 2026-11-14 trên **dev** (15 câu có đáp án + 2 câu thiếu evidence), model `gpt-4o-mini`, temperature 0. Tiêu chí chọn đã ghi trước ở [STEP5_PROTOCOL.md](STEP5_PROTOCOL.md).

## 1. Bốn cấu hình

| Mã | Retrieval | Agent | Ghi chú |
|---|---|---|---|
| B0 | hybrid unit (RRF dense unit + BM25) | 2 lượt, budget 4.000 | baseline |
| C1 | hybrid_day6 (RRF dense paragraph Day 6 → unit + BM25) | như B0 | sửa giả thuyết cắt 512 token |
| C2 | hybrid unit | 3 lượt, budget 6.000 | sửa giả thuyết context quá hẹp |
| C3 | hybrid unit | 3 lượt, budget 6.000, block cap 1.400 (trích cửa sổ câu) | sinh ra từ phân tích lỗi q11 |

## 2. Kết quả

| Cấu hình | Grounded 0/1/2 | Điểm TB /2 | Citation hợp lệ | Câu có citation | Từ chối đúng | Từ chối nhầm | Token (in+out) | Chi phí | Thời gian |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| B0 | 4/1/10 | 1,40 | 12/16 (75%) | 11/11 | 2/2 | 4/15 | 26.428 + 2.461 | 0,0054 USD | 78,2 s |
| C1 | 3/2/10 | 1,47 | 12/14 (86%) | 12/12 | 2/2 | 3/15 | 28.989 + 2.320 | 0,0057 USD | 74,0 s |
| **C2** | **1/2/12** | **1,73** | 15/19 (79%) | 14/14 | 2/2 | **1/15** | 40.198 + 2.738 | 0,0077 USD | 82,6 s |
| C3 | 2/3/10 | 1,53 | 14/17 (82%) | 13/13 | 2/2 | 2/15 | 32.193 + 2.625 | 0,0064 USD | 73,6 s |

Phân bố số lượt gọi: B0 15×1 + 2×2; C1 14×1 + 3×2; **C2 15×1 + 1×2 + 1×3**; C3 17×1.

Retrieval tương ứng (dev, 15 câu):

| Phương pháp | Hit@1 | Evidence Hit@3 | Context Evidence Rate |
|---|---:|---:|---:|
| hybrid (nhánh B0/C2) | 8/15 | 12/15 | 9/15 |
| hybrid_day6 (nhánh C1) | 9/15 | 12/15 | 8/15 |

## 3. Phân tích hai lỗi dev

**Lỗi 1 — q11 (censorship of fiction): gold có trong top-5 nhưng bị loại khỏi context.**
Trace B0: `hybrid_search` trả về `rep-b3-u037, rep-b2-u005, rep-b2-u024 (gold), rep-b3-u039, rep-b2-u023`, nhưng `context_ids` chỉ còn `[rep-b3-u037, rep-b2-u005]` vì budget 4.000 ký tự chỉ chứa 2 unit ~1.800 ký tự. Model trả lời trung thực "context không có thông tin" → bị chấm 0.
Nguyên nhân gốc: **chính sách chọn context**, không phải retrieval. Thử: nới budget (C2) và trích cửa sổ câu (C3). Kết quả: C2 và C3 đều trả lời đúng q11.

**Lỗi 2 — q17 (myth of the metals): chạm giới hạn lượt tìm.**
Trace B0: `max_searches=2`, model search 2 lần (lần 2 vẫn không có gold trong context) → `search_limit`. Nới lên 3 lượt (C2) vẫn không cứu được: gold `rep-b3-u041` xếp thứ 4 trong kết quả, vẫn ngoài context. Đây là **lỗi còn mở**: với câu hỏi ngắn, thuật ngữ chung ("myth of the metals") BM25 và dense đều không đưa đúng unit lên đầu. Hướng khắc phục đề xuất (chưa áp dụng để tránh tinh chỉnh quá mức trên 15 câu dev): rerank bằng overlap evidence, hoặc query expansion có kiểm soát.

**Quan sát thêm:** ở B0, q13 từ chối vì "invalid citations" — model viết câu trả lời nhưng không chèn `[id]` vào text; đây là lỗi định dạng mà C2/C3 không mắc. Không sửa bằng code vì sửa sẽ làm mất tín hiệu về việc model không tuân thủ định dạng.

## 4. Chốt cấu hình

Theo tiêu chí đã công bố (ưu tiên 1: chất lượng câu trả lời; ưu tiên 3: không tăng từ chối nhầm):

**Chọn C2** — `hybrid` (RRF dense unit + BM25, k=60, depth=20), `max_searches=3`, `context_budget=6000`, `top_k=5`, `temperature=0`, `max_tokens=900`.

- Cao nhất về grounded answer (1,73/2 so với 1,40–1,53) và 12/15 câu đạt mức 2.
- Từ chối nhầm giảm từ 4/15 xuống 1/15; từ chối đúng câu thiếu evidence vẫn 2/2.
- Giá phải trả: token +52% và chi phí +42% so với B0 (0,0077 so với 0,0054 USD cho 17 câu), thời gian gần như không đổi.
- C1 và C3 loại vì điểm thấp hơn rõ rệt (chênh ≥2 câu mức 2) dù C1 rẻ hơn.

Cấu hình này được đóng băng trước khi chạy test; mọi thay đổi sau khi xem kết quả test phải tạo benchmark v2 theo [BENCHMARK.md](../BENCHMARK.md).

## 5. Giới hạn

- Dev chỉ 15 câu có đáp án; chênh 1 câu = 6,7%. Khoảng cách C2 so với C3 là 2 câu mức 2, đủ để chọn nhưng vẫn trong sai số nhỏ.
- Nhãn do người làm bài chấm, có bảng chấm tay lưu tại `artifacts/day7/reviews/dev-*.md`; không dùng LLM judge.
- Citation "hợp lệ" được hiểu là: id có trong context **và** đoạn được cite thật sự chứa ý mà câu trả lời dựa vào; đã đọc từng câu khớp nhất trong bảng chấm.
- Câu a02 ở C2 từ chối đúng nhưng lý do ghi là `search_limit` (hết 3 lượt) chứ không phải kết luận "tài liệu không có"; hành vi đúng, lý do chưa đẹp — ghi nhận trong báo cáo.
