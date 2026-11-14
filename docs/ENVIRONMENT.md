# Môi trường chạy Day 7

## Phiên bản đã dùng

| Thành phần | Giá trị |
|---|---|
| OS | Windows (PowerShell 5.1) |
| Python | 3.13.17 (CPython) |
| venv | `.venv/` ở thư mục gốc repo (đã gitignore) |
| chromadb | 1.5.9 |
| fastembed | 0.9.1 |
| numpy | 2.5.4 |
| Embedding model | `BAAI/bge-small-en-v1.5` qua fastembed, 384 chiều, vector đã chuẩn hoá L2, metric cosine |
| Model cache | `artifacts/day6/fastembed_cache` (64 MB, bản `Qdrant/bge-small-en-v1.5-onnx-Q`, đã gitignore) |

Lock đầy đủ mọi package phụ: [artifacts/day6/rebuild/requirements.lock.txt](../artifacts/day6/rebuild/requirements.lock.txt).

## Cách dựng lại môi trường trên máy khác

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Lần chạy đầu, fastembed sẽ tải model (~64 MB) vào cache mặc định; nếu muốn cố định cache trong repo thì đặt biến môi trường `FASTEMBED_CACHE_PATH` hoặc truyền `cache_dir` (code Day 7 đang trỏ tới `artifacts/day6/fastembed_cache`).

## Ghi chú về sandbox của agent

Trong phiên làm bài, lệnh chạy dưới sandbox của agent bị chặn `os.chmod`, nên:

- `python -m venv .venv` hỏng ở bước `ensurepip` (temp dir không xoá được);
- `pip install` hỏng khi giải nén wheel vào temp.

Cách xử lý đã dùng (chỉ ảnh hưởng máy này, không ảnh hưởng repo):

1. Tạo venv bằng `python -m venv .venv`, bỏ qua pip lỗi;
2. Trích pip từ wheel có sẵn của Python (`Lib/ensurepip/_bundled/pip-*.whl`) vào `.venv/Lib/site-packages`;
3. Copy `site-packages` của venv Day 6 (đúng pin chromadb 1.5.9 / fastembed 0.9.1) sang `.venv`.

Hệ quả cần biết khi chạy test: `tests/test_baseline.py::test_cli_uses_requested_split_only` dùng `tempfile.TemporaryDirectory` và dọn temp bằng `chmod`, nên báo `PermissionError` dưới sandbox dù logic đúng. Chạy lại trong PowerShell thường (không sandbox) sẽ pass; phần hành vi của test đã được kiểm lại thủ công.

## Lệnh kiểm tra nhanh

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests   # starter tests
.\.venv\Scripts\python.exe src/validate_benchmark.py        # benchmark hợp lệ?
.\.venv\Scripts\python.exe src/check_absence.py             # bằng chứng câu thiếu evidence
```
