# Báo cáo Day 7

**MSSV:** 2A202603417 · **Họ tên:** Nguyễn Tuấn Kiệt · **Repo:** K5-L3A-DAY07-NguyenTuanKiet-2A202603417-RetrievalContext

## Dữ liệu và benchmark

- **Nguồn và quyền sử dụng:** *The Republic*, Plato, bản dịch Benjamin Jowett, Project Gutenberg eBook #1497 (<https://www.gutenberg.org/ebooks/1497>), public domain theo Project Gutenberg License. Phạm vi dùng: Books I–III (bỏ Introduction/Analysis và Books IV–X).
- **Số trang và số chunk:** 111 unit nội dung, 202.927 ký tự (~37.700 từ), mỗi unit là nhóm đoạn ≥1.500 ký tự — tương đương hơn 30 trang nội dung hợp lệ. Nguồn là text nên **không có số trang in**; `page` trong dữ liệu là thứ tự unit (1..111) và được ghi rõ trong `data/day6/manifest.json`. Đây là giới hạn phải nêu, không phải số trang giả.
- **Vector store và embedding:** ChromaDB 1.5.9, metric cosine, lưu tại `artifacts/day7/chroma` (collection `day7_units_384`, 111 vector). Embedding: fastembed `BAAI/bge-small-en-v1.5`, 384 chiều, chuẩn hoá L2, chạy local. Dựng index 28,0 s, chi phí 0 USD. Dùng lại đúng model và thư viện của Day 6; collection Day 6 (`republic_B_384`, 184 chunk paragraph) giữ nguyên để làm ablation về granularity.
- **Agent model và cách chạy:** `gpt-4o-mini`, temperature 0, max_tokens 900, prompt cố định `day7-agent-v1`, ba tool retrieval. Chạy bằng `python src/run_agent.py --split {dev|test} --include-abstain`. Key đọc từ `.env` (đã gitignore), không có trong repo.
- **Phân chia dev/test:** dev 17 câu (15 có đáp án + 2 thiếu evidence), test 7 câu (5 + 2). Test kế thừa 5 câu Day 6 đã tạo trước khi có pipeline Day 7 và 2 câu thiếu evidence viết trước khi chạy cấu hình nào; hash đóng băng trong `data/day6/benchmark_manifest.json`, kiểm bằng `python src/validate_benchmark.py` (luôn trả `errors=0`, kể cả sau khi chạy test).
- **Cách xác định câu có/thiếu evidence:** câu có đáp án lấy từ Day 6, mỗi câu có `gold` gồm `source_id`, `page`, `evidence` là **substring nguyên văn** của đúng unit — `src/adapt_day6.py` và `src/validate_benchmark.py` chặn nếu sai. Bốn câu thiếu evidence được viết mới, kiểm vắng mặt bằng keyword scan + top-5 lexical + top-5 dense rồi **đọc từng hit** trước khi xác nhận (`data/day6/abstain_checks.json`); cosine gần nhất 0,66–0,70 nghĩa là retriever vẫn trả về đoạn cùng chủ đề, nên đây không phải câu dễ trống.
- **Tiêu chí chấm:** grounded answer 0 = sai hoặc thiếu evidence, 1 = đúng một phần, 2 = đúng và đủ; từ chối câu có đáp án = 0. Citation hợp lệ = id có trong context **và** đoạn được cite thật sự hỗ trợ điều kiện trong câu trả lời (đọc tay, không chỉ kiểm ID). Abstention đúng = từ chối câu thiếu evidence kèm lý do khớp. Tiêu chí chọn cấu hình được ghi **trước** khi chạy: [docs/STEP5_PROTOCOL.md](../../docs/STEP5_PROTOCOL.md).

## Retrieval và thử nghiệm

### So sánh phương pháp trên dev (15 câu có đáp án, cùng 111 unit)

| Cấu hình | Phương pháp, top-k, filter | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
|---|---|---|---|---:|---:|---:|---|
| Dense unit | bge-small 384d, cosine, top-3 | baseline dense đúng hợp đồng Day 7 | dev | 3/15 (20,0%) | 10/15 (66,7%) | 7/15 (46,7%) | 14,8 ms/query, 0 USD |
| BM25 | BM25Okapi k1=1,5 b=0,75, top-3 | lexical có mạnh hơn dense trên văn bản cổ không | dev | **10/15 (66,7%)** | 11/15 (73,3%) | **10/15 (66,7%)** | 1,6 ms/query, 0 USD |
| Hybrid RRF | RRF(dense, bm25), k=60, depth=20 | hợp nhất hai thang điểm bằng thứ hạng | dev | 8/15 (53,3%) | **12/15 (80,0%)** | 9/15 (60,0%) | 19,9 ms/query, 0 USD |
| Ablation: dense Day 6 | dense trên `republic_B_384` rồi gộp về unit | unit dài > 512 token bị cắt nên dense unit yếu | dev | 6/15 (40,0%) | 11/15 (73,3%) | 9/15 (60,0%) | 16,5 ms/query, 0 USD |
| Hybrid + nhánh Day 6 | RRF(dense Day 6 → unit, bm25) | nhánh dense tốt hơn có kéo Hit@1 lên không | dev | 9/15 (60,0%) | 12/15 (80,0%) | 8/15 (53,3%) | 37,3 ms/query, 0 USD |

Filter chỉ dùng metadata `book` (3 câu dev, 2 câu test), cấp trước khi truy xuất và không chứa gold. Nhóm filter dev: dense 1/3, dense Day 6 2/3, bm25 2/3, hybrid 1/3 (Hit@1).

**Đọc kết quả:** BM25 mạnh nhất về Hit@1 vì câu hỏi Day 6 dùng nhiều từ khoá trùng bản dịch Jowett — đây là benchmark thiên từ vựng, phải nói rõ. Hybrid có Evidence Hit@3 cao nhất nhưng Hit@1 thấp hơn BM25. Dense unit yếu vì `bge-small-en-v1.5` chỉ nhận 512 token trong khi unit dài 1.502–4.762 ký tự; ablation lật ngược giả thuyết bằng số liệu (3/15 → 6/15).

### Cấu hình agent trên dev (17 câu) — 3 thử nghiệm cải thiện

| Cấu hình | Phương pháp, context budget, số lượt | Giả thuyết / thay đổi | Split | Grounded TB /2 | Từ chối nhầm | Hit@3 của nhánh retrieval | Chi phí |
|---|---|---|---|---:|---:|---|---:|
| B0 | hybrid unit, budget 4.000, 2 lượt | baseline | dev | 1,40 | 4/15 | 12/15 | 0,0054 USD |
| C1 | hybrid Day 6, budget 4.000, 2 lượt | sửa cắt 512 token | dev | 1,47 | 3/15 | 12/15 | 0,0057 USD |
| **C2** | hybrid unit, budget 6.000, 3 lượt | context chứa được nhiều unit hơn | dev | **1,73** | **1/15** | 12/15 | 0,0077 USD |
| C3 | hybrid unit, budget 6.000, block cap 1.400 | trích cửa sổ câu để chứa 4 unit | dev | 1,53 | 2/15 | 12/15 | 0,0064 USD |

### Hai lỗi dev, nguyên nhân và kết quả sau khi sửa

1. **q11 (censorship of fiction) — gold nằm trong top-5 nhưng bị loại khỏi context.** Trace: hybrid trả `rep-b3-u037, rep-b2-u005, rep-b2-u024 (gold), rep-b3-u039, rep-b2-u023`, nhưng `context_ids` chỉ còn 2 unit đầu vì budget 4.000 ký tự không đủ cho unit thứ ba (~1.800 ký tự). Model từ chối trung thực → 0 điểm. **Nguyên nhân là chính sách chọn context, không phải retrieval.** Đã thử nới budget (C2) và trích cửa sổ câu (C3); cả hai trả lời đúng q11.
2. **q17 (myth of the metals) — chạm giới hạn lượt tìm.** Với 2 lượt, model search 2 lần rồi bị `search_limit`; lần 2 gold `rep-b3-u041` vẫn chỉ xếp thứ 4. Nới 3 lượt (C2) vẫn không cứu được vì gold ngoài context. **Lỗi còn mở**: câu hỏi ngắn, thuật ngữ chung nên cả BM25 và dense không đưa đúng unit lên đầu; hướng khắc phục đề xuất là rerank theo overlap evidence hoặc query expansion, nhưng tôi **không** tinh chỉnh thêm để tránh overfit 15 câu dev.

### Chọn cấu hình

Chốt **C2**: `hybrid` (RRF k=60, depth=20) trên 111 unit, `max_searches=3`, `context_budget=6.000`, `top_k=5`, temperature 0.

- Tiêu chí ưu tiên 1 (chất lượng câu trả lời): 1,73/2, cao hơn baseline 0,33 và hơn C3 0,20 — tương đương 2 câu mức 2.
- Tiêu chí ưu tiên 3 (không từ chối nhầm): 1/15 so với 4/15; từ chối đúng câu thiếu evidence giữ 2/2.
- Đánh đổi: token +52%, chi phí +42% (0,0054 → 0,0077 USD cho 17 câu), thời gian gần như không đổi (78,2 → 82,6 s). Chấp nhận được vì vẫn dưới 1 cent cho toàn bộ dev.
- C1 và C3 bị loại vì điểm thấp hơn rõ rệt dù C1 rẻ hơn; nếu ưu tiên chi phí tuyệt đối thì C1 là phương án dự phòng.

## Agent và đánh giá

- **Tool và điều kiện dừng:** ba tool `dense_search`, `lexical_search`, `hybrid_search`; model chọn tool và query, **filter do harness cấp từ câu hỏi** nên không thể tự suy ra gold. Dừng khi: model trả `answer` có citation hợp lệ; model trả `abstain`; hết `max_searches=3`; hết `max_steps=5`; hoặc citation không nằm trong context (→ abstain, không trả lời).
- **Chọn context:** dedup theo id, giữ thứ tự hạng qua các lượt search, đóng gói block `[id | source | page N]` cho tới khi đầy budget 6.000 ký tự; không cắt giữa câu ở cấu hình chốt. Đã đo context budget 800 của starter: **Context Evidence Rate 0/15** vì unit dài hơn budget, nên không dùng.
- **Xử lý lỗi:** lỗi provider/tool → `status='error'` kèm `events[].stage`, không thay bằng câu trả lời giả. Output không phải JSON → thử repair một lần (thêm ở bước 5 vì một ca q19 trả `"...")` thiếu ngoặc), nếu vẫn hỏng thì ghi lỗi.

| Cấu hình / split | Tool use | Số lượt gọi (TB / max) | Grounded 0/1/2, TB | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
|---|---|---:|---|---:|---:|---:|---:|
| B0 / dev | 17/17 | 1,12 / 2 | 4/1/10 — 1,40 | 12/16 | 11/11 | 2/2 | 4/15 |
| C1 / dev | 17/17 | 1,18 / 2 | 3/2/10 — 1,47 | 12/14 | 12/12 | 2/2 | 3/15 |
| **C2 / dev** | 17/17 | 1,18 / 3 | **1/2/12 — 1,73** | 15/19 | 14/14 | 2/2 | **1/15** |
| C3 / dev | 17/17 | 1,00 / 1 | 2/3/10 — 1,53 | 14/17 | 13/13 | 2/2 | 2/15 |
| B0 / test | 7/7 | 1,00 / 1 | 2/1/2 — 1,00 | 1/6 | 3/3 | 2/2 | 2/5 |
| **C2 / test** | 7/7 | 1,14 / 2 | **1/1/3 — 1,40** | 3/6 | 4/4 | 2/2 | **1/5** |

### Chấm từng câu test (C2)

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| q04 | paraphrase, craft analogy | hybrid 1 lượt; gold `rep-b1-u022` không vào top-5 | Trả lời đúng nguyên lý (người cai trị phục vụ người bị trị, ví dụ shepherd) `[rep-b1-u018][rep-b1-u023]` | **2**; citation thứ nhất không hỗ trợ (u018 nói về nghĩa vụ tuân lệnh), thứ hai có |
| q07 | direct, ring of Gyges | hybrid 2 lượt; gold `rep-b2-u003` (4.762 ký tự) vào top-1 nhưng bị budget loại | Nói đúng "tàng hình khi xoay collet" nhưng `[rep-b2-u002][rep-b2-u005]` không chứa đoạn Gyges | **1**; nội dung đúng nhưng **không có evidence trong context**, citation sai — trả lời từ kiến thức sẵn có |
| q10 | direct, nguồn gốc chiến tranh | hybrid 1 lượt; gold `rep-b2-u018` top-1, vào context | Đúng: thành phố xa hoa cần thêm đất → chiến tranh `[rep-b2-u018]` | **2**; citation hợp lệ |
| q14 | condition/exception, quá nhiều music | hybrid 1 lượt; gold `rep-b3-u035` xếp thứ 4, context đầy trước | Từ chối: "context không có thông tin" | **0**; từ chối nhầm do retrieval xếp hạng, không do thiếu tri thức |
| q18 | condition/exception, ngoại lệ kim loại | hybrid 1 lượt; gold `rep-b3-u041` vào context | Đúng: không di truyền tuyệt đối, có thể chuyển tầng `[rep-b3-u041]` | **2**; citation hợp lệ |
| a03 | thiếu evidence (nuptial number) | hybrid 1 lượt; không có đoạn trả lời | Từ chối kèm lý do "context không có nuptial number Book VIII" | Đúng; không thêm khẳng định vô căn cứ |
| a04 | thiếu evidence (tổng số guardian) | hybrid 1 lượt | Từ chối kèm lý do "context không nêu tổng số guardian" | Đúng |

Chấm context test (0 = không có evidence, 1 = có nhưng thiếu điều kiện/nguồn, 2 = đủ evidence và nguồn): B0 được 0/0/2/0/0; C2 được 0/0/2/0/2 trên q04/q07/q10/q14/q18.

- **Đường dẫn trace, nhãn, lệnh chạy:** `artifacts/day7/results/agent-{dev|test}-{b0,c1,c2,c3}/` (mỗi thư mục có `traces.json`, `cases.json`, `run_meta.json`, `agent_metrics.json`); nhãn chấm tay `artifacts/day7/reviews/{dev,test}-*.md` và `*-reviews.json`; bảng context `test-*-context_grades.json`. Lệnh chạy đầy đủ ở [src/README.md](../../src/README.md).
- **Thời gian và chi phí:** dev 78,2 s / 0,0077 USD (C2), test 30,3 s / 0,0027 USD (C2). Tổng toàn bộ thử nghiệm agent của bài: ~0,030 USD. Median độ trễ mỗi câu dev 4,7 s, test 4,2 s (chủ yếu là gọi model, retrieval < 40 ms).
- **Kết quả trước/sau:** cùng 7 câu test, C2 so với baseline tăng grounded 1,00 → 1,40, citation 1/6 → 3/6, giảm từ chối nhầm 2/5 → 1/5, chi phí +33%.
- **Ví dụ lỗi và giới hạn:** (a) q07 cho thấy câu trả lời đúng chưa chứng minh grounded — context không chứa đoạn Gyges mà vẫn trả lời trôi chảy; (b) 3/5 câu test có context grade 0, nguyên nhân chính là chọn context theo budget ký tự cứng, unit dài bị bỏ nguyên khối; (c) citation hợp lệ chỉ 3/6 vì model hay cite unit lân cận; (d) a03/a04 từ chối đúng nhưng ở dev ca a02 từng từ chối vì `search_limit` thay vì kết luận thiếu bằng chứng — hành vi đúng, lý do chưa đẹp. Không có số liệu nào bị thay bằng kết quả giả; các ca lỗi provider (1 ca q19 trước khi thêm repair) được ghi riêng và đã sửa gốc.

## Thử thách nâng cao

Không thực hiện. Lý do: phần cơ bản đã cho thấy lỗi cốt lõi nằm ở chính sách chọn context (unit dài bị loại), và thử thách 100 trang có bảng/ảnh/biểu đồ cần một pipeline OCR/trích bảng riêng cùng benchmark mới; làm thêm khi chưa sửa lỗi nền sẽ chỉ nhân bản lỗi đó. Nếu làm tiếp, hướng ưu tiên là (1) chọn context theo câu thay vì theo unit, (2) rerank có kiểm soát độ dài, (3) xử lý unit > 4.000 ký tự bằng cửa sổ trượt — tất cả phải đánh giá lại trên **benchmark v2**, không dùng lại test hiện tại.
