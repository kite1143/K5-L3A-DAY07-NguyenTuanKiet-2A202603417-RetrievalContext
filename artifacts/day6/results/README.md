# Kết quả bước 2

## tfidf-dev — baseline lexical trên dev

Lệnh:

```powershell
python starter/baseline.py --chunks data/day6/chunks.json `
  --questions data/day6/questions.json --split dev `
  --output artifacts/day6/results/tfidf-dev
```

Kết quả (`summary.json`):

| Chỉ số | Giá trị |
|---|---|
| n | 15 |
| Hit@1 | 7/15 (46,7%) |
| Evidence Hit@3 | 13/15 (86,7%) |
| Context Evidence Rate | 0/15 |
| avg_context_chars | 0 |
| index_seconds | 0,028 |
| chi phí | 0 USD (TF-IDF local) |

**Vì sao context rỗng:** `starter/baseline.py` dùng `pack_context(budget=800)`, trong khi unit Day 6 dài 1.500–2.000 ký tự, nên không block nào vừa budget và context luôn rỗng. Đây là hành vi đúng của code mẫu, không phải lỗi dữ liệu. Bước 3 phải tự chọn context budget (ví dụ 3.000–6.000 ký tự) và báo Context Evidence Rate theo budget đó.

**Chưa chạy test:** theo BENCHMARK.md, test chỉ chạy sau khi chốt cấu hình trên dev.
