# Báo cáo Day 7 — Agentic RAG

**Học viên:** Lê Hoàng Sơn · **MSSV:** 2A202603662 · **Lớp:** L3A

Tóm tắt: agent dùng Gemini (function calling) tìm bằng chứng trong index Day 6 bằng 3 công cụ (dense, từ khóa BM25, hybrid RRF), trả lời có trích dẫn hoặc từ chối. Cấu hình được chọn trên dev (A2: 3 công cụ, context budget 6000 ký tự) đạt điểm grounded trung bình 2,00/2 trên test (9 câu) so với 0,44/2 của baseline (A0: chỉ dense, budget 800), nhưng trả lời một câu thiếu bằng chứng mà đáng lẽ phải từ chối (abstention 2/3). Test chỉ có 9 + 3 câu và mỗi cấu hình chỉ chạy một lần nên mọi kết luận cần đọc cùng phần "Giới hạn".

## Dữ liệu và benchmark

- **Nguồn, quyền sử dụng, số trang và số chunk:** 3 văn bản pháp luật công khai: Luật An ninh mạng 24/2018/QH14, Luật Giao dịch điện tử 2023, Nghị định 13/2023/NĐ-CP; 87 trang nội dung; 240 chunk (chiến lược B của Day 6: theo Điều/khoản, tối đa 1200 ký tự). Nguồn PDF và manifest nằm trong repo Day 6, không đưa vào repo này.
- **Vector store, embedding, phiên bản và số chiều:** ChromaDB 1.5.9 (`PersistentClient`, HNSW xấp xỉ, cosine), collection `lab_B`; embedding `intfloat/multilingual-e5-small`, 384 chiều, mean pooling + L2, tiền tố `query:`/`passage:`, chạy CPU. Python 3.12.10, torch 2.15.0, transformers 5.22.2, numpy 2.5.4. Retriever dense của Day 7 tái dùng đúng index và cách nhúng truy vấn của Day 6 (kiểm tra: Hit@1 13/15 và Hit@3 15/15 trên 15 câu dev đầu, khớp số liệu Day 6).
- **Agent model, cách chạy, dev/test:** `gemini-3.5-flash-lite` qua `google-genai` 3.3.0, `temperature = 0`, function calling chế độ `ANY` (free tier). Dev: 28 câu (25 có đáp án + 3 thiếu bằng chứng). Test: 12 câu (9 có đáp án + 3 thiếu bằng chứng). Dev gồm 15 câu Day 6, 5 câu Day 6 từng được dùng làm "test" (nên chuyển sang dev vì đã bị dùng để so sánh chiến lược ở Day 6) và 5 câu mới. Test gồm 9 + 3 câu viết mới, chưa chạy với bất kỳ hệ thống nào trước khi chốt cấu hình. Chi tiết: [data/benchmark.md](../../data/benchmark.md).
- **Cách xác định câu có/thiếu evidence và tiêu chí chấm:** mỗi câu có đáp án có trích dẫn evidence được script [scripts/build_benchmark.py](../../scripts/build_benchmark.py) kiểm tra nằm đúng trang gốc và nằm trong ít nhất một chunk. Câu có nhiều evidence ghi `gold_mode: all` (cần đủ mọi trích dẫn, tính trên hợp các chunk). Câu thiếu bằng chứng gần chủ đề (ví dụ số năm lưu trữ, mức phạt, DPO) có regex phải cho 0 kết quả trên toàn corpus, kèm lý do. Chấm câu trả lời theo thang 0/1/2 của BENCHMARK.md; trích dẫn chấm đúng/sai từng cái bằng cách đọc đoạn được trích.
- **Sử dụng AI (khai báo):** mã nguồn, 20 câu hỏi mới của benchmark và bản nháp nhãn chấm (dev và test) do Claude Code (Claude Sonnet 5.5) soạn; người học đọc và duyệt nhãn trước khi tổng hợp (các ghi chú `NHÁP-AI` trong `reviews.csv` đánh dấu nguồn gốc nháp). Tôi đã đối chiếu thủ công các câu test t06–t14, u04–u06 với PDF gốc.

## Retrieval và thử nghiệm

**Retrieval thuần (không agent), truy vấn gốc, không filter, top-3, cùng index/câu hỏi.** Hit@1/Hit@3 không phụ thuộc budget; Context Evidence Rate tính trên top-3 đóng gói theo budget.

| Cấu hình | Phương pháp | Giả thuyết | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate (b800 / b3000) | Thời gian (ms, trung vị) |
|---|---|---|---|---|---|---|---|
| Baseline | Dense (Day 6, `lab_B`) | — | dev (25) | 21/25 | 24/25 | 9/25 / 24/25 | 16,9 / 17,5 |
| Phương pháp 2 | BM25, âm tiết (`uni`) | Từ khóa khớp tốt vì luật dùng nguyên văn | dev (25) | 21/25 | 25/25 | 8/25 / 25/25 | 1,2 / 1,4 |
| Phương pháp 2b | BM25, âm tiết + bigram (`unibi`) | Bigram xấp xỉ từ ghép tiếng Việt | dev (25) | 21/25 | 25/25 | 8/25 / 25/25 | 2,2 / 1,8 |
| Phương pháp 3 | Hybrid RRF dense + `uni` | Hợp nhất thứ hạng bù điểm yếu của từng bên | dev (25) | 21/25 | 25/25 | 8/25 / 25/25 | 19,7 / 17,7 |
| Phương pháp 3b | Hybrid RRF dense + `unibi` | như trên | dev (25) | 21/25 | 24/25 | 8/25 / 24/25 | 18,9 / 18,4 |

Trên dev, các phương pháp gần như không phân biệt được (Hit@3 24–25/25). Hybrid không tốt hơn BM25 đơn thuần; bigram không giúp. Ghi nhận: chỉ khác biệt ở các câu nhiều văn bản (d17) và câu diễn đạt xa luật (d18, BM25 thắng dense).

**Agent (Gemini tự chọn công cụ và số lượt tìm).** Hit@k của agent không tính được tương đương vì agent tự viết lại truy vấn; so sánh bằng Context Evidence Rate của context cuối. Mọi cấu hình dùng cùng model, `top_k = 3`, `max_searches = 4`, `max_steps = 8`.

| Cấu hình | Phương pháp, budget | Giả thuyết / thay đổi | Split | Context Evidence Rate | Grounded 0/1/2 (TB /2) | Token (vào + ra) | Thời gian |
|---|---|---|---|---|---|---|---|
| A0 Baseline | dense, 800 ký tự | Cấu hình tối giản (mặc định của starter) | dev | 8/25 | 16/1/8 (0,68) | 141.621 + 7.040 | 468 s |
| A1 | dense + BM25 + hybrid, 3000 | Nhiều công cụ và ngân sách lớn hơn giúp giữ đủ chunk | dev | 22/25 | 1/3/21 (1,80) | 141.045 + 7.276 | 286 s |
| A2 Cải thiện 1 | như A1, 6000 | Chunk đúng bị loại do hết budget (d13, d17) sẽ vào context | dev | 25/25 | 0/1/24 (1,96) | 141.685 + 7.075 | 304 s |
| A3 Cải thiện 2 | như A1 + quy tắc id trong prompt | Quy tắc "chép nguyên văn id" giảm id trích dẫn bịa | dev | 24/25 | 0/2/23 (1,92) | 140.762 + 7.329 | 282 s |
| **Cấu hình đã chọn (A2)** | như trên | Chốt trước test | **test** | **9/9** | **0/0/9 (2,00)** | 78.363 + 3.425 | 123 s |
| Baseline (A0) | như trên | — | **test** | 2/9 | 7/0/2 (0,44) | 69.018 + 2.951 | 163 s |

**Retrieval thuần trên test (9 câu có đáp án, cấu hình đã chốt, chạy một lần):**

| Phương pháp | Hit@1 | Evidence Hit@3 | Context Evidence Rate (b800 / b6000) |
|---|---|---|---|
| Dense | 5/9 | 7/9 | 2/9 / 7/9 |
| BM25 `uni` | 6/9 | 8/9 | 3/9 / 8/9 |
| BM25 `unibi` | 7/9 | 8/9 | 3/9 / 8/9 |
| Hybrid RRF dense + `uni` | 6/9 | 7/9 | 2/9 / 7/9 |
| Hybrid RRF dense + `unibi` | 6/9 | 8/9 | 2/9 / 8/9 |

Context Evidence Rate của agent A2 (9/9) cao hơn mọi retrieval một lượt (tối đa 8/9) vì agent gom context qua nhiều lượt tìm. Thời gian là tổng của cả bộ; chi phí tiền: dùng free tier nên không phát sinh phí; số token đã ghi ở bảng. Chênh lệch dưới 2 câu không được coi là bằng chứng.

### Hai lỗi dev, nguyên nhân, cách thử và lý do chọn cấu hình

1. **Chunk đúng bị loại do hết ngân sách context (d13, d17).** Trong A1, chunk đúng (`Điều24:1` cho d13, `Điều41:0` cho d17) xuất hiện ở lượt tìm 2 nhưng bị loại vì context đã gần đầy sau lượt tìm đầu; d17 bị trả lời thiếu một nửa (điểm 1), d13 trả lời bằng Điều 13 (hệ thống quan trọng) thay vì Điều 24 (điểm 1). Giả thuyết: tăng budget lên 6000. Kết quả A2: cả hai vào context và được trả lời đúng (điểm 2); Context Evidence Rate 22/25 → 25/25, token gần như không đổi (141.045 → 141.685) vì agent dừng sớm hơn (d13: 4 → 2 lượt tìm).
2. **Id trích dẫn bịa (t02, t05).** Model tự suy ra id chưa từng được truy xuất (ví dụ `Điều21:1`, `Điều21:2` khi chỉ có `Điều21:0`), dù nội dung trả lời đúng. Giả thuyết A3: thêm quy tắc "chép nguyên văn id". Kết quả: **không cải thiện** (id bịa 3/29 so với 2/27 ở A1; t05 vẫn bịa 2 id; ở u03, A3 còn trích dẫn 2 id không tồn tại ngay trong câu từ chối, lỗi mà chỉ số trích dẫn không bắt được vì câu từ chối không có trích dẫn). Giả thuyết bị bác bỏ.
3. **Ghi chú: t03 trong A1 không phải lỗi truy xuất cố định.** A1 không lấy được `Điều12:0` và khẳng định sai ("không có chiều ngược lại"), nhưng A2 và A3 lấy được chunk này chỉ trong 1 lượt tìm (điểm 2). Không có thay đổi nào của ta nhắm vào t03, nên đây là dao động giữa các lần chạy, không phải tác dụng của budget hay quy tắc id.

**Lý do chọn cấu hình** (tiêu chí chốt trước test, [docs/experiment_protocol.md](../../docs/experiment_protocol.md): điểm grounded trung bình, rồi trích dẫn hợp lệ, rồi token): A2 (1,96; 26/27) trước A3 (1,92; 26/29) và A1 (1,80; 24/27). Cơ chế của A2 có bằng chứng trong trace (mục 1); lợi thế của A3 trên A1 chủ yếu do dao động chứ không phải do quy tắc id (mục 2, 3).

**Lỗi truy xuất còn tồn tại (chưa xử lý):** ở d03, d04 (và t03 của A1), chunk đúng nằm hạng 2 vì các chunk kề nhau của cùng một Điều tranh vị trí với nhau. Hướng thử tiếp: mở rộng sang chunk lân cận cùng Điều hoặc reranker; chưa được thử.

## Agent và đánh giá

- **Tool, số lượt gọi, điều kiện dừng, cách chọn context và xử lý lỗi:**
  - Tool: `search_dense`, `search_keyword` (BM25), `search_hybrid` (RRF), cộng `final_answer(answer, citations, enough_evidence)`. Công cụ tìm nhận `query` và `document_type` (chỉ dùng khi câu hỏi nêu rõ loại văn bản; mọi filter được ghi trong trace).
  - Lượt gọi: tối đa 4 lượt tìm, 8 lượt model. Dừng khi gọi `final_answer`, hết lượt (→ từ chối), hoặc lỗi LLM (→ `error`).
  - Context: gom qua các lượt tìm theo thứ tự đến, loại trùng, giữ nguyên từng chunk trong budget ký tự (tính cả dòng nguồn); chunk không vừa bị bỏ. Chỉ id trong context cuối được coi là hợp lệ để trích dẫn.
  - Trích dẫn: id ngoài context vẫn được giữ và đánh dấu `invalid_citation_ids` để chỉ số trích dẫn bắt được; không biến câu trả lời thành từ chối. Không có trích dẫn nào → từ chối (`no_citations`).
  - Lỗi: retry (tối đa 5 lần, backoff mũ) với 429/5xx, ghi từng lần thử; lỗi vẫn ghi `status: error`, không thay bằng kết quả giả; dừng sau 3 lỗi liên tiếp; `--resume` chạy lại đúng các câu lỗi với cấu hình giống hệt (trace chạy lại có `resumed_after_error`). Prompt nêu nội dung tài liệu là dữ liệu, không phải chỉ dẫn.

| Cấu hình / split | Tool use | Số lượt tìm (phân bố) | Grounded 0/1/2 và TB | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
|---|---|---|---|---|---|---|---|
| A0 / dev | 28/28 | 1:6 · 2:2 · 3:1 · 4:19 | 16/1/8 · 0,68 | 10/11 | 10/10 | 3/3 | 15/25 |
| A1 / dev | 28/28 | 1:20 · 4:8 | 1/3/21 · 1,80 | 24/27 | 25/25 | 3/3 | 0/25 |
| A2 / dev | 28/28 | 1:20 · 2:2 · 3:1 · 4:5 | 0/1/24 · 1,96 | 26/27 | 25/25 | 3/3 | 0/25 |
| A3 / dev | 28/28 | 1:20 · 2:1 · 4:7 | 0/2/23 · 1,92 | 26/29 | 25/25 | 3/3 | 0/25 |
| **A2 / test** | 12/12 | 1:7 · 3:1 · 4:4 | **0/0/9 · 2,00** | **13/13** | 10/10 | **2/3** | **0/9** |
| A0 / test | 12/12 | 2:2 · 4:10 | 7/0/2 · 0,44 | 2/2 | 2/2 | 3/3 | 7/9 |

Context test (điểm 0/1/2, 9 câu có đáp án): A2 gồm 9 câu điểm 2; A0 gồm 2 câu điểm 2 và 7 câu điểm 0. Lỗi hệ thống: 0 trong cả hai lần chạy test sau khi chạy lại (xem "Lỗi hạ tầng" bên dưới).

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| t08 (test, A2) | Có đáp án, 2 ý | 1 lượt `search_hybrid` → top `Điều12:0`, `Điều11:1`, `Điều16:0` | Thông báo hậu quả rút lại đồng ý + ngừng xử lý [`nd-13-2023:Điều12:0`] | Grounded 2; citation đúng (cả hai ý ở khoản 3, 4); context 2 |
| u05 (test, A2) | Thiếu bằng chứng | 4 lượt (`search_hybrid`, 2 × `search_keyword`, `search_dense`) không thấy quy định xếp hạng | Từ chối: các văn bản không có quy định về bảng xếp hạng; không trích dẫn | Abstention đúng (không thêm khẳng định vô căn cứ) |
| u04 (test, A2) | Thiếu bằng chứng, **lỗi** | 4 lượt `search_hybrid` → tìm thấy `Điều13:1` (thời hạn lưu trữ theo pháp luật về lưu trữ) | Trả lời "hợp đồng điện tử là thông điệp dữ liệu; thời hạn lưu trữ theo pháp luật về lưu trữ" [`Điều3:2`, `Điều13:1`]; không nói rõ corpus không nêu số năm | Abstention **sai**: `enough_evidence=true`. Không bịa số năm nhưng không nêu rõ thiếu bằng chứng (đúng tiêu chí của lab). Ghi chú: câu trả lời trung thực, ranh giới mong manh |
| t06 (test, A0) | Có đáp án, từ chối nhầm | 4 lượt `search_dense`; context chỉ có 1 chunk (`Điều23:0`) vì budget 800 loại 2–3 chunk mỗi lượt, kể cả `Điều13:1` | Từ chối ("không đủ bằng chứng") | Grounded 0 (từ chối câu có đáp án); context 0. Lỗi do ngân sách, không phải do model |
| d17 (dev, A1 → A2) | Nhiều văn bản | A1: 4 lượt, `Điều41:0` bị loại 3 lần; A2: `Điều41:0` vào context ở lượt đầu | A1 chỉ nửa Nghị định 13; A2 đủ cả Luật An ninh mạng và Nghị định 13 | A1: 1; A2: 2 |
| t05 (dev, A1) | Id bịa | 1 lượt `search_hybrid` → `Điều21:0` | Nội dung đúng, nhưng trích dẫn thêm `Điều21:1`, `Điều21:2` không tồn tại | Grounded 2; citation `1 0 0` |

- **Đường dẫn:** retrieval thuần dev: `results/retrieval-dev25-b800`, `results/retrieval-dev25-b3000`; test: `results/retrieval-test-b800`, `results/retrieval-test-b6000`. Agent dev: `results/agent-dev-{A0-dense-b800, A1-all-b3000, A2-all-b6000, A3-all-b3000-citerule}`; test: `results/agent-test-{A0-dense-b800, A2-all-b6000}`. Mỗi thư mục có `traces.jsonl` (từng tool call, tham số, kết quả, context, câu trả lời, citation, token, thời gian, lỗi), `summary.json`, và `review/` (phiếu chấm `sheet.md`, nhãn `reviews.csv`, tổng hợp `summary.json`).
- **Lệnh chạy, thời gian, chi phí:** xem "Cách tái lập". Thời gian từng cấu hình ở bảng phía trên; chỉ ghi số token, chưa tính tiền (free tier).
- **Lỗi hạ tầng (báo riêng, không loại khỏi mẫu số):** lần chạy đầu của A2 (11/28 câu lỗi) và A3 (28/28) gặp lỗi 429 hết hạn mức 500 yêu cầu/ngày của free tier; chúng được chạy lại bằng `--resume` với khóa API của một project khác. Ở test, A0 (u04) và A2 (u06) mỗi cấu hình gặp một lỗi 429 vượt 15 yêu cầu/phút (retry của runner không đủ lâu), được chạy lại bằng `--resume`; không có lỗi nào ảnh hưởng đến kết quả chất lượng. A0 và A1 trên dev đã chạy hai lần: lần đầu dùng chính sách cũ (id trích dẫn ngoài context bị biến thành từ chối), sau đó đổi sang chính sách hiện tại (giữ và đánh dấu id lạ). Chỉ kết quả của lần chạy sau được báo cáo; kết quả lần đầu chỉ lưu cục bộ, không đưa vào repo.
- **Kết quả trước/sau, ví dụ lỗi, đánh đổi và giới hạn:**
  - Trước/sau: A0 → A1 → A2 trên dev nâng điểm grounded từ 0,68 lên 1,80 rồi 1,96; trên test A0 → A2: 0,44 → 2,00. Phần lớn lợi ích đến từ ngân sách context lớn hơn, không phải từ việc thêm công cụ: A0 từ chối nhầm 15/25 (dev) và 7/9 (test) vì chỉ một chunk vừa budget 800.
  - Đánh đổi: A2 tốn nhiều token hơn A0 trên test (+14% tổng token: 81.788 so với 71.969) nhưng nhanh hơn (123 s so với 163 s) vì ít lượt tìm lặp. Cái giá chất lượng của A2: abstention 2/3 so với 3/3 của A0 (A0 từ chối cả khi có đáp án, nên 3/3 không phản ánh hiệu chuẩn tốt).
  - Giới hạn: xem mục cuối.

## Thử thách nâng cao (nếu thực hiện)

Không thực hiện.

## Giới hạn

- **Mẫu nhỏ, một lần chạy:** dev 25 + 3, test 9 + 3 câu; mỗi cấu hình chạy một lần dù `temperature = 0` (đã quan sát dao động: t02 lúc có lúc không bịa id; t03 lúc đúng lúc sai). Chênh lệch dưới 2 câu không phải bằng chứng.
- **Benchmark có thiên lệch:** câu hỏi do một người (kèm AI) soạn, diễn đạt gần câu chữ trong luật nên BM25 mạnh; các câu gắn thẻ `lexical-gap` chưa làm BM25 yếu đi. Kết luận "dense/hybrid không hơn BM25" chỉ đúng với benchmark này.
- **Nhãn do AI soạn nháp:** dev và test được chấm nháp bởi AI rồi người học duyệt; đây không phải hai người chấm độc lập. Một số quyết định chấm có thể tranh cãi (d14 "sau" so với "trong vòng" 72 giờ; u04; u06; t06).
- **Chỉ số trích dẫn chưa bắt hết id bịa:** id bịa trong câu trả lời bị từ chối (ví dụ u03 của A3) không vào chỉ số trích dẫn.
- **Chưa thử:** mở rộng chunk lân cận, reranker, query decomposition tường minh, nhiều model; chưa tính chi phí tiền (free tier); chưa chạy thử thách nâng cao.

## Cách tái lập

```bash
# môi trường: Python 3.12, cài gói (xem requirements.txt), đặt GEMINI_API_KEY trong .env (xem .env.example)
# Day 6: cần index Chroma ở K5-L3A-Day06-.../starter/results/chroma (dựng bằng `python -m src.index` trong repo Day 6) hoặc đặt DAY6_DIR
python scripts/export_day6.py                      # chunks.json + questions_day6.json
python scripts/build_benchmark.py                  # kiểm chứng evidence -> questions.json
python -m rag.evaluate --split dev --budget 3000 --out results/retrieval-dev25-b3000
python -m rag.run_agent --split dev --name A2-all-tools-b6000 --tools dense,bm25,hybrid --budget 6000 --out results/agent-dev-A2-all-b6000
python scripts/make_review_sheet.py --traces results/agent-dev-A2-all-b6000/traces.jsonl
python scripts/finalize_reviews.py --traces results/agent-dev-A2-all-b6000/traces.jsonl --split dev
# test (chỉ sau khi chốt cấu hình; xem docs/experiment_protocol.md):
python -m rag.run_agent --split test --confirm-final --name T-A2-all-tools-b6000 --tools dense,bm25,hybrid --budget 6000 --out results/agent-test-A2-all-b6000
python -m unittest discover -s tests -v            # test mock, chỉ kiểm tra code (Windows: đặt PYTHONUTF8=1)
```
