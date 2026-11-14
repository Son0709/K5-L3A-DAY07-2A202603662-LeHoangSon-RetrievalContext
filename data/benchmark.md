# Benchmark Day 7 (corpus pháp luật, 87 trang)

Corpus: Luật An ninh mạng 2018 (`luat-anm-2018`), Luật Giao dịch điện tử 2023 (`luat-gddt-2023`), Nghị định 13/2023/NĐ-CP (`nd-13-2023`). Index: Day 6, chiến lược B (240 chunk). Dựng lại bằng:

```bash
python scripts/export_day6.py       # chunks.json + questions_day6.json
python scripts/build_benchmark.py   # kiểm chứng trên văn bản gốc -> questions.json, benchmark_report.json
```

| Split | Có đáp án | Thiếu bằng chứng | Nguồn |
|---|---:|---:|---|
| dev | 25 | 3 (u01-u03) | 15 câu Day 6 (d01-d15) + 5 câu Day 6 "test" đã bị xem (t01-t05) + 5 câu mới (d16-d20) |
| test | 9 (t06-t14) | 3 (u04-u06) | viết mới, chưa chạy với bất kỳ retriever nào |

- **t01-t05 được chuyển sang dev** (`origin: day6-test-seen`) vì Day 6 đã dùng chúng để so sánh chiến lược. Test độc lập là t06-t14 và u04-u06.
- Tôi (người soạn câu hỏi) đã đọc các Điều liên quan khi soạn test; chưa chạy test với retriever nào. Mọi cấu hình phải chốt trên dev trước khi chạy test (`--confirm-final`).
- `gold_mode`: `any` = một trích dẫn là đủ, `all` = cần đủ mọi trích dẫn (8 câu, có cả bằng chứng nằm ở nhiều chunk hoặc nhiều văn bản). Hit@k tính trên hợp các chunk trong top-k.
- Trang của mỗi trích dẫn được script tìm và kiểm tra là duy nhất (hoặc khai báo tường minh) trên văn bản trang gốc; mỗi trích dẫn phải nằm trong ít nhất một chunk để lỗi là của retrieval chứ không phải của chunking.
- Câu thiếu bằng chứng: mỗi câu có `absence_checks` (regex) phải có 0 kết quả trên toàn corpus, và `absence_reason` giải thích vì sao gần chủ đề nhưng không có đáp án. Kiểm tra bằng regex không thay thế việc đọc: u02, u04 có điều khoản liên quan nhưng không nêu thời hạn cụ thể.

## Giới hạn
- 25 câu dev và 9 câu test là mẫu nhỏ; chênh lệch 1 câu không phải bằng chứng thống kê.
- Nhiều câu hỏi vẫn dùng từ ngữ gần với văn bản luật, nên lexical search (BM25) vẫn mạnh. Các câu gắn thẻ `lexical-gap` (diễn đạt khác văn bản) chưa làm BM25 yếu đi trong thử nghiệm đầu.
- Các câu hỏi do một người soạn, có thiên lệch theo cách diễn đạt của người đó.
