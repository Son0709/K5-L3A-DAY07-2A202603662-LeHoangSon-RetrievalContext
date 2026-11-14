# Chốt cấu hình và tiêu chí trước khi chạy test

Ngày chốt: 2026-11-14. Văn bản này phải được commit **trước** khi chạy bất kỳ lệnh nào với `--split test` / `--confirm-final`. Sau khi chạy test không được sửa cấu hình, prompt, benchmark hay tiêu chí; nếu cần sửa thì phải tạo bộ test mới và ghi rõ.

## 1. Kết quả dev đã dùng để chọn (28 câu: 25 có đáp án + 3 thiếu bằng chứng)

| Cấu hình | Công cụ | Budget (ký tự) | Prompt | Grounded 0/1/2 | TB /2 | Trích dẫn hợp lệ | Abstention đúng | Từ chối nhầm |
|---|---|---:|---|---|---:|---|---|---|
| A0 baseline | dense | 800 | gốc | 16/1/8 | 0,68 | 10/11 | 3/3 | 15/25 |
| A1 | dense + bm25 + hybrid | 3000 | gốc | 1/3/21 | 1,80 | 24/27 | 3/3 | 0/25 |
| A2 | dense + bm25 + hybrid | 6000 | gốc | 0/1/24 | 1,96 | 26/27 | 3/3 | 0/25 |
| A3 | dense + bm25 + hybrid | 3000 | gốc + quy tắc id | 0/2/23 | 1,92 | 26/29 | 3/3 | 0/25 |

Nhãn dev do AI soạn nháp rồi được người học đọc và duyệt. Mỗi cấu hình dev chỉ chạy một lần (ngoại trừ A1 chạy hai lần; các lần chạy cho thấy kết quả dao động nhỏ dù `temperature = 0`), nên chênh lệch dưới 2 câu không đủ kết luận. Lần chạy đầu của A2 (11/28 câu) và A3 (28/28 câu) gặp lỗi hết quota 429 và đã được chạy lại bằng `--resume`.

## 2. Tiêu chí chọn (đã áp dụng theo thứ tự)

1. Điểm grounded answer trung bình (/2) cao hơn.
2. Nếu bằng nhau: tỷ lệ trích dẫn hợp lệ cao hơn.
3. Nếu vẫn bằng nhau: ít token hơn, rồi ít thời gian hơn.

Theo tiêu chí này A2 (1,96) được chọn, trước A3 (1,92) và A1 (1,80). Lý do giả thuyết của A2 được ủng hộ: trong A1, chunk đúng của d13 (Điều 24) và d17 (Điều 41:0) bị loại do hết ngân sách context; trong A2 hai chunk này vào context và hai câu được trả lời đúng. Giả thuyết của A3 (quy tắc id trích dẫn) **không** được ủng hộ: số id bịa không giảm (3/29 so với 2/27).

## 3. Cấu hình chốt để chạy test

| | Baseline (A0) | Cấu hình chọn (A2) |
|---|---|---|
| Model | `gemini-3.5-flash-lite`, `temperature = 0` | như A0 |
| Công cụ | `search_dense` | `search_dense`, `search_keyword`, `search_hybrid` |
| top_k | 3 | 3 |
| Context budget | 800 ký tự | 6000 ký tự |
| max_searches / max_steps | 4 / 8 | 4 / 8 |
| Prompt | `SYSTEM` (không có `CITE_RULE`) | như A0 |
| Index | Day 6 `lab_B`, multilingual-e5-small | như A0 |

Lệnh chạy:

```bash
python -m rag.run_agent --split test --confirm-final --name T-A0-dense-b800 --tools dense --budget 800 --out results/agent-test-A0-dense-b800
python -m rag.run_agent --split test --confirm-final --name T-A2-all-tools-b6000 --tools dense,bm25,hybrid --budget 6000 --out results/agent-test-A2-all-b6000
python -m rag.evaluate --split test --confirm-final --budget 800  --out results/retrieval-test-b800
python -m rag.evaluate --split test --confirm-final --budget 6000 --out results/retrieval-test-b6000
```

Nếu một lần chạy gặp lỗi hệ thống (quota, mạng), dùng `--resume` với cấu hình giống hệt; lỗi vẫn được báo riêng và không loại khỏi mẫu số.

## 4. Đánh giá test (người học thực hiện)

- Test gồm 9 câu có đáp án (t06–t14) và 3 câu thiếu bằng chứng (u04–u06). Chạy mỗi cấu hình một lần.
- Chấm tay mọi câu test cho cả A0 và A2: `answer_grade` 0/1/2, `citation_support` cho từng trích dẫn, `abstention_correct`, và `context_score` 0/1/2 cho ít nhất 5 câu có đáp án. Nhãn AI soạn nháp (nếu dùng) phải được người học đọc đối chiếu nguồn và ghi rõ trong báo cáo.
- Báo `n/N` cho mọi chỉ số, kể cả kết quả không cải thiện, cùng token, thời gian, số lần retry và lỗi hệ thống. Chi phí bằng tiền chưa tính (free tier); số token đã được ghi.

## 5. Giới hạn đã biết

- Dev nhỏ (25 + 3 câu) và một lần chạy mỗi cấu hình; kết quả có dao động giữa các lần chạy.
- Câu hỏi do một người soạn nên diễn đạt gần văn bản luật; BM25 vẫn mạnh và lợi thế của dense/hybrid khó thấy.
- Test nhỏ (9 + 3 câu): chênh lệch 1 câu không phải bằng chứng thống kê.
- Chưa thử xử lý lỗi truy xuất do chunk lân cận (mở rộng chunk cùng Điều) hay reranker.
