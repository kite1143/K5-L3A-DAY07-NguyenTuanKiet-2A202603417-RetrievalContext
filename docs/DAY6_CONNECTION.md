# Nối Day 6 → Day 7

Day 7 dùng lại đúng dữ liệu, ID, nguồn, embedding model và vector store của Day 6; không tạo vector ngẫu nhiên và không huấn luyện lại index.

## 1. Nguồn dữ liệu

| Trường | Giá trị |
|---|---|
| Tài liệu | *The Republic*, Plato, bản dịch Benjamin Jowett |
| Nguồn | Project Gutenberg eBook #1497 — <https://www.gutenberg.org/ebooks/1497> |
| Quyền dùng | Public domain (USA) theo Project Gutenberg License; đã ghi trong `data/day6/raw/day6_data_manifest.json` |
| Phạm vi | Books I–III (bỏ Introduction/Analysis và Books IV–X) |
| Đơn vị nội dung | 111 unit, mỗi unit là nhóm đoạn ≥ 1.500 ký tự; tổng 202.927 ký tự |
| File gốc | `data/day6/raw/corpus.jsonl` (kèm `units.csv`, manifest Day 6) |

"page" trong Day 7 = **thứ tự unit** (1..111), không phải số trang in: nguồn là text Gutenberg, không có phân trang. Quy ước này giữ nguyên từ Day 6 và được ghi trong `data/day6/manifest.json`.

## 2. Embedding và vector store

| Trường | Giá trị |
|---|---|
| Provider | fastembed (local, không gọi API, chi phí 0 USD) |
| Model | `BAAI/bge-small-en-v1.5` (bản ONNX quantized của Qdrant) |
| Số chiều | 384, đã chuẩn hoá L2 |
| Vector store | ChromaDB 1.5.9, persistent, metric cosine |
| Đường dẫn | `artifacts/day6/chroma` (copy từ Day 6, gitignore) |
| Collection dùng cho Day 7 | `republic_B_384` — 184 chunk kiểu paragraph (target 1500 / min 300 ký tự) |
| Collection đối chứng | `republic_A_384` — 498 chunk fixed 500/50, giữ để so sánh chunking |

Chi phí embedding Day 6: 41,68 s cho 498 + 184 chunk trên máy local, 0 USD (xem `data/day6/raw/day6_benchmark_manifest.json` và `starter/results/run_config.json` bên Lab_06).

## 3. Chuyển schema sang Day 7

`src/adapt_day6.py` đọc corpus Day 6 và sinh ra:

| File | Nội dung |
|---|---|
| `data/day6/chunks.json` | 111 chunk theo schema Day 7: `id, text, source_id, source, page, metadata` |
| `data/day6/questions.json` | 20 câu có đáp án (15 dev / 5 test), `gold` là list `{source_id, page, evidence, unit_id}` |
| `data/day6/manifest.json` | nguồn, sha256 file gốc, thống kê, embedding/store, field mapping, giới hạn |

Ánh xạ trường:

- `id` ← `unit_id`; `source_id` ← `document_id`; `page` ← `page` (unit index)
- `metadata` ← `book, book_title, section, author, language, start_char, end_char, char_count`
- `gold[0].evidence` ← `evidence_quote`; `gold[0].unit_id` ← `gold_unit_id` (giữ để truy vết)

Script tự kiểm tra: evidence là substring của đúng unit, `gold_page` khớp `page` của unit, id duy nhất, page liên tục 1..111.

## 4. Chạy lại

```powershell
python src/adapt_day6.py     # sinh lại chunks.json + questions.json + manifest.json

python starter/baseline.py `
  --chunks data/day6/chunks.json `
  --questions data/day6/questions.json `
  --split dev `
  --output artifacts/day6/results/tfidf-dev
```

Muốn dựng lại vector store (khi không copy `artifacts/day6/chroma`): dùng code Day 6 trong `artifacts/day6/rebuild/` (chunking, ingestion, embeddings, store) với cùng corpus và cùng pin package — thời gian ~42 s trên CPU.

## 5. Giới hạn phải ghi trong báo cáo

- Một tài liệu duy nhất, tiếng Anh; không có PDF gốc nên không có số trang in.
- Unit ~1.500 ký tự nên evidence gần như luôn nằm trọn trong một chunk; trường hợp bị cắt phải ghi riêng khi phân tích lỗi.
- Baseline TF-IDF của Day 7 dùng context budget 800 ký tự, nhỏ hơn một unit Day 6 (~1.500–2.000 ký tự) nên **context rỗng** với dữ liệu này. Đây là lý do phải tự chọn context budget ở bước 3, không dùng mặc định.
