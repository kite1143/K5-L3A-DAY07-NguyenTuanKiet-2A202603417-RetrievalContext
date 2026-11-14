# Định dạng dữ liệu

Các file `example_*.json` chỉ minh họa định dạng, không đủ để nộp bài. Dữ liệu thật là JSON array UTF-8; nếu dùng định dạng khác, ghi cách chuyển trong README.

- **Chunk:** `id`, `text`, `source_id`, `source`, `page`, `metadata`. ID phải duy nhất; giữ phiên bản hoặc ngày nếu có.
- **Câu có đáp án:** `id`, `split` (`dev` hoặc `test`), `question`, `expected_answer`, `gold`: danh sách `{source_id, page, evidence}`. Với schema mẫu, mỗi evidence phải nằm trọn trong một chunk đúng nguồn và trang; các phần tử `gold` là evidence thay thế. Với câu multi-hop cần nhiều đoạn, bạn có thể mở rộng schema, ghi rõ nhóm evidence bắt buộc và cách chấm. Có thể thêm `filter` do người dùng cung cấp trước.
- **Câu thiếu evidence:** `id`, `split`, `question`, `answerable: false`, `expected_behavior: "search_and_abstain"`, `absence_reason`. Xem `agent_cases_example.json`.

Không đưa `gold` hoặc nhãn đáp án vào model và retrieval tool. Ghi nguồn dữ liệu và quyền sử dụng. Cách chuyển một số định dạng Day 6: [starter/README.md](../starter/README.md).
## Dữ liệu dùng trong bài

Bộ dữ liệu thật nằm ở [`day6/`](day6/), chuyển từ Lab_06 (Plato, *The Republic*, Books I–III, Project Gutenberg #1497 — public domain):

- [`day6/chunks.json`](day6/chunks.json) — 111 chunk, schema Day 7.
- [`day6/questions.json`](day6/questions.json) — 20 câu có đáp án (15 dev / 5 test).
- [`day6/abstain.json`](day6/abstain.json) — 4 câu thiếu evidence (2 dev / 2 test).
- [`day6/manifest.json`](day6/manifest.json) — nguồn, sha256, embedding và store.
- [`day6/benchmark_manifest.json`](day6/benchmark_manifest.json) — hash đóng băng của benchmark.

Cách chuyển và giới hạn: [docs/DAY6_CONNECTION.md](../docs/DAY6_CONNECTION.md). Quy ước chấm: [docs/BENCHMARK_DAY7.md](../docs/BENCHMARK_DAY7.md).
