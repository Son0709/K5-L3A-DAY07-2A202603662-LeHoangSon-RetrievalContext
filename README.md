# Day 7 — Agentic RAG

**Bài cá nhân · Python 3.11+ · tiếp nối Day 6**

Dùng embedding và vector store từ Day 6 để xây một agent biết tìm bằng chứng, trả lời có nguồn và nhận biết khi không đủ thông tin. Bạn tự chọn kiến trúc, số tool và cách tổ chức retrieval.

> **Tùy chọn:** [Gợi ý dùng AI để lập trình](AGENT_SETUP.md) giúp bạn làm lab; phần này không bắt buộc và không tính điểm.

## Bài cần làm

![Agent tìm tài liệu trong kho Day 6 và trả lời có nguồn](assets/retrieval-pipeline.svg)

1. Kết nối dữ liệu, embedding và vector store Day 6.
2. Xây agent dùng model thật và ít nhất một khả năng truy xuất dữ liệu. Agent có thể dùng nhiều tool và nhiều lượt gọi.
3. Thử **ít nhất 3 phương pháp retrieval khác nhau**, trong đó có dense retrieval dùng vector store Day 6. Tự chọn các phương pháp còn lại; xem [gợi ý](GUIDE.md#2-thử-các-phương-pháp-retrieval).
4. Thử nhiều cấu hình, benchmark, phân tích lỗi và chọn cấu hình tốt trên **dev**; sau đó đánh giá trên **test**.

Benchmark tối thiểu có **24 câu**: dev gồm 15 câu có đáp án và 2 câu thiếu bằng chứng; test gồm 5 câu có đáp án và 2 câu thiếu bằng chứng. Xem [benchmark](BENCHMARK.md) và [rubric](RUBRIC.md).

## Thử thách nâng cao · +15 điểm

Index một tài liệu thực tế từ **100 trang** có bảng, ảnh và biểu đồ; xây agent truy xuất và trả lời các câu hỏi về nội dung đó. Hoàn thành [thử thách nâng cao](ADVANCED.md) và đạt **ít nhất 90% benchmark test** để nhận 15 điểm bonus. Phần cơ bản tối đa 85 điểm; toàn bài tối đa 100 điểm.

## Bắt đầu

1. Đọc [hướng dẫn](GUIDE.md), [rubric](RUBRIC.md) và [quy tắc](RULES.md).
2. Tạo repo cá nhân theo [cách nộp bài](SUBMISSION.md), chuẩn bị đầu ra Day 6 và model hỗ trợ tool calling.
3. Dùng hoặc thay thế [starter](starter/README.md); bạn cần kết nối model và vector store thật.
4. Chạy `python -m unittest discover -s tests -v`. Test mock chỉ kiểm tra code, không phải benchmark agent thật.

![Các bước thử nghiệm trên dev và đánh giá trên test](assets/experiment-loop.svg)

Nộp code, cách chạy, cấu hình, benchmark, trace và [báo cáo](report/individual/MSSV_HoTen.md). Thời gian ở [checkpoints](CHECKPOINTS.md) là gợi ý, có thể điều chỉnh theo lớp và phạm vi thử nghiệm.

---

# Bài nộp của học viên — Lê Hoàng Sơn (2A202603662)

Agent Gemini (`gemini-3.5-flash-lite`, function calling) tra cứu 3 văn bản pháp luật (Luật An ninh mạng 2018, Luật Giao dịch điện tử 2023, Nghị định 13/2023/NĐ-CP; 87 trang, 240 chunk) trên index Day 6 (ChromaDB + `multilingual-e5-small`). Ba phương pháp retrieval: dense (index Day 6), BM25 (hai cách tách từ) và hybrid RRF. Cấu hình chọn trên dev (3 công cụ, context budget 6000 ký tự) đạt grounded 2,00/2 trên test (9 câu có đáp án) so với 0,44/2 của baseline (chỉ dense, 800 ký tự), nhưng trả lời một câu thiếu bằng chứng lẽ ra phải từ chối (abstention 2/3). Test nhỏ (9 + 3 câu) và mỗi cấu hình chạy một lần; xem phần giới hạn trong báo cáo.

**Báo cáo:** [report/individual/2A202603662_LeHoangSon.md](report/individual/2A202603662_LeHoangSon.md)

## Cấu trúc và đường dẫn

| Nội dung | Đường dẫn |
|---|---|
| Retrieval (dense, BM25, hybrid RRF) và đánh giá Hit@k, Context Evidence Rate | `rag/dense.py`, `rag/lexical.py`, `rag/hybrid.py`, `rag/evaluate.py` |
| Agent (vòng lặp, công cụ, context, trace), client Gemini | `rag/agent.py`, `rag/tools.py`, `rag/llm.py`, `rag/run_agent.py` |
| Benchmark (dev 25 + 3, test 9 + 3), nguồn gốc và giới hạn | `data/questions.json`, `data/benchmark.md`, `data/benchmark_report.json` |
| Dựng và kiểm chứng benchmark, phiếu chấm, tổng hợp nhãn | `scripts/` |
| Cấu hình và tiêu chí chốt trước khi chạy test | `docs/experiment_protocol.md` |
| Kết quả: trace từng tool call, nhãn chấm tay, tổng hợp | `results/` (mỗi thư mục có `traces.jsonl`, `summary.json`, `review/`) |
| Test mock (chỉ kiểm tra code, không phải kết quả đánh giá) | `tests/` |

## Cách chạy (Python 3.12, đã dùng trên Windows)

```bash
python -m venv .venv            # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env            # điền GEMINI_API_KEY (file .env không được commit)
```

Cần index Day 6 (ChromaDB `lab_B`). Mặc định code tìm ở `K5-L3A-Day06-.../starter/results/chroma` cạnh thư mục này; repo Day 6 nằm ngoài git của repo này. Dựng lại bằng `python -m src.index` trong repo Day 6, hoặc đặt biến môi trường `DAY6_DIR` trỏ tới repo đó.

```bash
python scripts/export_day6.py        # chuyển chunk/câu hỏi Day 6 sang schema Day 7
python scripts/build_benchmark.py    # kiểm chứng evidence trên văn bản gốc, tạo data/questions.json
python -m rag.evaluate --split dev --budget 3000 --out results/retrieval-dev25-b3000
python -m rag.run_agent --split dev --name A2-all-tools-b6000 --tools dense,bm25,hybrid --budget 6000 --out results/agent-dev-A2-all-b6000
python scripts/make_review_sheet.py --traces results/agent-dev-A2-all-b6000/traces.jsonl   # phiếu chấm tay
python scripts/finalize_reviews.py --traces results/agent-dev-A2-all-b6000/traces.jsonl --split dev
python -m unittest discover -s tests -v   # Windows: đặt PYTHONUTF8=1
```

Chạy `--split test` cần thêm `--confirm-final` và chỉ nên làm sau khi chốt cấu hình (xem `docs/experiment_protocol.md`). Nếu gặp lỗi hạn mức API (429), runner tự dừng sau 3 lỗi liên tiếp; chạy lại đúng lệnh đó với `--resume` để chỉ chạy các câu còn lỗi.

## Ghi chú

- Mã nguồn, 20 câu hỏi mới của benchmark và bản nháp nhãn chấm được soạn với sự hỗ trợ của AI (Claude Code); nhãn được học viên đọc và duyệt (ghi chú `NHÁP-AI` trong `reviews.csv`). Chi tiết ở báo cáo.
- Model chạy qua API (free tier); số token từng lần chạy được lưu trong `summary.json`, chi phí tiền chưa tính.
- Kết quả có thể lệch nhẹ giữa các lần chạy dù `temperature = 0`.
- Không thực hiện thử thách nâng cao.
