# Benchmark Day 7

Benchmark v1 dùng cho phần cơ bản, chia dev/test, đã đóng băng hash trong [data/day6/benchmark_manifest.json](../data/day6/benchmark_manifest.json).

## 1. Thành phần

| Nhóm | Dev | Test | Tổng | Nguồn |
|---|---:|---:|---:|---|
| Có đáp án | 15 | 5 | 20 | Day 6 `benchmark/questions.jsonl` (đã kiểm evidence) |
| Thiếu evidence | 2 | 2 | 4 | Bổ sung Day 7, viết trước khi chạy pipeline |
| **Tổng** | **17** | **7** | **24** | |

Yêu cầu tối thiểu của BENCHMARK.md là 17 dev / 7 test; bộ này đúng bằng ngưỡng cho câu có đáp án và đủ 2 dev + 2 test cho câu thiếu evidence.

## 2. Câu thiếu evidence và cách kiểm chứng

Không kết luận "thiếu bằng chứng" chỉ vì top-k không tìm thấy. Với từng câu, `src/check_absence.py` ghi lại:

1. top-5 chunk gần nhất theo TF-IDF (lexical);
2. top-5 chunk gần nhất theo dense (Chroma `republic_B_384`) kèm cosine;
3. số lần xuất hiện của từng thuật ngữ chủ đề và unit chứa nó.

Kết quả: [data/day6/abstain_checks.json](../data/day6/abstain_checks.json). Người làm bài đọc từng hit rồi xác nhận `review.decision = confirmed_absent` trong [data/day6/abstain.json](../data/day6/abstain.json).

| ID | Split | Câu hỏi | Cosine gần nhất | Lý do vắng mặt |
|---|---|---|---:|---|
| a01 | dev | Tuổi Socrates khi nói chuyện với Cephalus? | 0,688 | Unit gần nhất chỉ nói tuổi già của Cephalus |
| a02 | dev | Ba làn sóng nghịch lý ở Book V? | 0,696 | Book V ngoài phạm vi corpus |
| a03 | test | Nuptial number ở Book VIII? | 0,667 | Book VIII ngoài phạm vi; chữ "nuptial" ở `rep-b2-u031` nói về đám cưới Thetis |
| a04 | test | Tổng số guardian của thành bang? | 0,661 | 22 hit "guardian" nhưng không có con số tổng |

Cosine gần nhất 0,66–0,70 nghĩa là retriever **có** trả về đoạn cùng chủ đề — câu hỏi không dễ lộ đáp án trống, agent phải thật sự từ chối.

## 3. Quy ước chấm

- Câu thiếu evidence **không** vào mẫu số Hit@1 / Evidence Hit@3 / Context Evidence Rate.
- **Hit@1**: chunk top-1 có `source_id` + `page` đúng và chứa nguyên văn `evidence`.
- **Evidence Hit@3**: một trong top-3 thoả cùng điều kiện.
- Nhiều đoạn thay thế hợp lệ: `gold` được phép là list; hiện mỗi câu có một evidence gốc từ Day 6.
- Evidence bị chunk cắt qua ranh giới: tính miss cho metric tự động, ghi vào phần phân tích lỗi.
- Filter chỉ dùng `book`, cấp trước khi truy xuất, không chứa unit/page gold.

## 4. Chính sách dev/test

- Test kế thừa nguyên trạng 5 câu của Day 6 (đã tạo trước khi có pipeline Day 7) cộng 2 câu thiếu evidence viết trước khi chạy bất kỳ cấu hình nào.
- Dev dùng để chọn cấu hình; test chỉ chạy sau khi chốt tiêu chí.
- Nếu buộc phải sửa test sau khi xem kết quả: tạo benchmark v2, báo riêng, không dùng lại test cũ như holdout độc lập.
- Hash đóng băng: `python src/validate_benchmark.py --freeze`; kiểm tra: `python src/validate_benchmark.py` sẽ báo lỗi nếu file đổi.

## 5. Kiểm tra tự động

```powershell
.\.venv\Scripts\python.exe src/validate_benchmark.py
```

Script chặn các lỗi: thiếu câu, sai split, evidence không nằm trong chunk đúng nguồn/trang, filter chứa gold, id trùng, evidence trùng, câu thiếu evidence bị tính vào mẫu số, hash lệch sau đóng băng.
