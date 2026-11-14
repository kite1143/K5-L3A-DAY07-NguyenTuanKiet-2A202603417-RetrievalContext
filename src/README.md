# Code Day 7

Code bước 2 (dữ liệu + benchmark). Retrieval, agent và đánh giá sẽ thêm ở các bước sau.

| File | Công dụng | Lệnh |
|---|---|---|
| `adapt_day6.py` | Chuyển corpus/benchmark Day 6 sang schema Day 7; kiểm tra evidence, page, id | `python src/adapt_day6.py` |
| `validate_benchmark.py` | Kiểm tra ràng buộc benchmark (20+ câu có đáp án, 4 câu thiếu evidence, filter, hash) | `python src/validate_benchmark.py [--freeze]` |
| `check_absence.py` | Ghi bằng chứng vắng mặt (lexical + dense + keyword) cho 4 câu thiếu evidence | `python src/check_absence.py` |

## Kết quả bước 2

```
chunks=111 characters=202927 by_book={1: 37, 2: 31, 3: 43}
questions=20 by_split={'dev': 15, 'test': 5} by_type={'condition_exception': 3, 'direct': 13, 'paraphrase': 4}
abstain=4 by_split={'dev': 2, 'test': 2}
```

Kiểm tra: `validate_benchmark.py` trả `errors=0`. Baseline TF-IDF trên dev: Hit@1 7/15, Hit@3 13/15 (context rỗng vì budget mặc định 800 ký tự < độ dài unit — xem `docs/DAY6_CONNECTION.md` mục 5).

## Cấu trúc dữ liệu

```
data/day6/
  raw/                     bản gốc Day 6 (corpus.jsonl, questions.jsonl, manifest, units.csv)
  chunks.json              111 chunk theo schema Day 7
  questions.json           20 câu có đáp án (15 dev / 5 test)
  abstain.json             4 câu thiếu evidence + review đã xác nhận
  abstain_checks.json      bằng chứng kiểm tra vắng mặt
  manifest.json            nguồn, hash, thống kê, embedding/store, giới hạn
  benchmark_manifest.json  hash đóng băng của bộ benchmark
```
