# Báo cáo Day 09 — Lê Văn Trung Tính, 2A202603145

## 1. Kết luận trước
Pipeline kết luận **HOLD**: **224 ảnh vào, 202 ảnh ra** `submission/export/clean_v1/` (bản **nháp**, chưa phát hành). Không còn lỗi bắt buộc (0 lỗi ở `07_error_list_v3`), nhưng **38/202 ảnh (18,8%) còn cảnh báo chưa người duyệt, vượt ngưỡng 10%** (ngân sách duyệt 80 ảnh, hàng đợi 125 ảnh). Lỗi bắt buộc đi từ 36 (vòng 1) → 6 (sau autofix, đều là ảnh thiếu file nhãn) → 0 (sau người duyệt).

## 2. Lỗi và phân việc
Số lấy từ `02_error_list_v1` (mẫu số: 224 ảnh quét; 202 ảnh sau cửa vào). Tổng 58 lỗi bắt buộc + 153 cảnh báo.

| Mã lỗi | Số lượng | Ai sửa | Vì sao |
|---|---:|---|---|
| CORRUPT_IMAGE 2, BAD_SIZE 3 | 5/224 ảnh | máy: loại ở cửa vào | ảnh không dùng được, không có gì để sửa |
| DUP_IMAGE_EXACT 8, DUP_IMAGE_NEAR 4 | 12/224 ảnh | máy: loại | trùng; giữ ảnh đầu, loại các bản sau |
| LEAK_TEST | 5/224 ảnh | máy: loại | trùng ảnh test/val sẽ làm số đo đẹp giả |
| BAD_CLASS_ID 6, BAD_FORMAT 3, BOX_ZERO 4, DUP_BOX 7 | 20 dòng | máy: `drop_line` | hỏng cú pháp, xoá dòng an toàn |
| BOX_OUT_OF_IMAGE | 8 dòng | máy: `clip_box` | cắt về [0,1], giữ lớp (8/8 còn diện tích) |
| BAD_CLASS_NAME | 2 mục | máy: `rename_classes` (1 fix) | ghi lại `names` đúng danh sách lớp |
| MISSING_LABEL_FILE | 6/202 ảnh | **người** | máy không bịa nhãn: `needs_label`, không tạo file rỗng |
| POSSIBLE_MISSING 53, FALSE_POS 29, LOOSE_BOX 28, WRONG_CLASS 18 | 128 cảnh báo | **người** | ngữ nghĩa: model lớn chỉ nghi ngờ, có thể sai |
| EMPTY_LABEL 12, BOX_TINY 6, CLASS_RARE 4, BOX_HUGE 3 | 25 cảnh báo | **người** | cần phán đoán (ảnh nền? vật quá nhỏ?) |

**Hàng đợi (`05_review_queue.csv`, 125 ảnh):** điểm ưu tiên = tổng trọng số cảnh báo × (1 + conf) + sửa tự động (`FIXED_*`) + `NEEDS_LABEL` (10 điểm). Ảnh đầu bảng là `img_0020` (11,5 điểm: vừa bị xoá dòng, vừa POSSIBLE_MISSING, vừa POSSIBLE_WRONG_CLASS); 6 ảnh thiếu nhãn (10 điểm, chỉ người gán được) nằm trong top 7. Ngân sách 80 ảnh duyệt đúng 80 ảnh đầu, **45 ảnh cuối không ai xem**. Trong 123 cảnh báo ngữ nghĩa sau autofix (`04_error_list_v2`), người xem được 94 (76%); 29 còn nằm ở ảnh chưa duyệt.

## 3. Calibration (2 ngưỡng)
Đo trên `data/calib` (39 ảnh, `submission/calibration/calibration_report.md`). P / R = precision / recall.

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | NEAR 1,00/0,50 → 1,00/0,67; EXACT 1,00/1,00 không đổi | Lỗi này bị **tự loại ảnh**, nên ưu tiên precision. Calib phẳng ở 4–14 (P=1,00, R=0,67); chọn 12 vì trên raw bắt thêm 2 cặp NEAR trùng thật so với dist 4 (cộng 1 ảnh LEAK_TEST mới mà tôi không xác minh được bằng mắt). Dist 16 bị loại (xem dưới). |
| `second_opinion.conf` | 0.25 | **0.6** | MISSING 0,50/1,00 → 0,57/1,00; WRONG_CLASS 0,56/0,83 → 0,62/0,83; LOOSE_BOX 0,29/0,40 → 0,20/0,20 (xấu đi); FALSE_POS 0,31/1,00 không đổi (dùng `fp_conf`) | Cảnh báo cho người nên ưu tiên recall: 0.6 là mức **cao nhất còn giữ recall MISSING = 1,00** (0.7 tụt 0,88; 0.8 tụt 0,75). Chấp nhận LOOSE_BOX yếu (F1 ≤ 0,46 ở mọi conf). |

Tác động trên raw (chạy thử bằng config tạm, không đổi `configs/`; tái lập: chép `configs/pipeline.yaml` vào `work/`, đổi 2 khoá rồi `python -m pipeline.run --config work/<file>.yaml --reports work/rX --export-dir work/eX --work work/wX`): (2; 0.25) → Hold 60/205 (29,3%), hàng đợi 145; **(12; 0.6) → Hold 38/202 (18,8%), hàng đợi 125**. Nếu chọn `conf=0.8` (phash 12) gate ra **Release** 16/202 (7,9%), nhưng chỉ vì hàng đợi co còn 102 ảnh và bỏ sót 25% POSSIBLE_MISSING: đó là "Release giả" nên **không chọn**.

**Chỗ calibration có thể đánh lừa:** trên calib `phash_dist=16` có F1 cao nhất (NEAR 0,91) và precision vẫn 1,00, nhưng calib chỉ có 6 ảnh gần trùng (mỗi ảnh nhảy 17% recall). Trên raw, so với dist 12, dist 16 thêm 3 cặp NEAR đều ở đúng mép 16: mở xem thì **2/3 là hai ảnh khác hẳn nhau** (`img_0011`↔`img_0008` quần vợt vs trượt tuyết; `img_0177`↔`img_0113` lướt sóng vs chân dung), chỉ `img_0084`↔`img_0074` là trùng thật (cắt khung). Số ảnh `LEAK_TEST` cũng nhảy 5 → 11 (không mở ảnh test để xác minh, vì RULES cấm dùng `data/test` để chọn ngưỡng). Ngược lại ở dist 12, 2 cặp thêm (`img_0186`↔`img_0061`, `img_0223`↔`img_0077`) đều là cùng cảnh, bị cắt/đổi sáng.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn thật.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không người duyệt nên 6 ảnh thiếu nhãn còn nguyên): kết luận **REWORK**, mã thoát **20**, còn 6 lỗi bắt buộc (`MISSING_LABEL_FILE`) và 112/202 ảnh (55,4%) còn cảnh báo; `work/exp_nb/` **không được tạo** (không xuất dataset). Lần `make run` thường (ngân sách 80) ra Hold, mã thoát 10, xuất bản nháp.

**(b) Điểm mù có bằng chứng:**
1. *Ảnh gần trùng biến đổi mạnh:* ở dist 12 calib bỏ sót 2/6 ảnh NEAR (R = 0,67). Chỉ nới lên 16 mới bắt thêm, nhưng đổi lại gộp nhầm ảnh khác nhau (mục 3): không có ngưỡng nào vừa bắt đủ vừa an toàn.
2. *Box lỏng:* `POSSIBLE_LOOSE_BOX` ở conf 0.6 chỉ đạt P = 0,20 / R = 0,20 trên calib (bắt 1/5 lỗi chèn), F1 tối đa 0,46 ở mọi conf: máy gần như không phân biệt được box lệch nhẹ.
3. *Báo động giả của ý kiến thứ hai:* `POSSIBLE_FALSE_POS` P = 0,31 (11 cảnh báo sai trên bộ calib nhãn người, do lệch tự nhiên giữa model và nhãn người); ngược lại máy không báo thiếu cho vật nhỏ hơn `min_area_px` (600 px²), nên vật nhỏ bị bỏ sót vô hình.
4. *Cảnh báo chưa ai xem:* 45 ảnh trong hàng đợi không được duyệt; bản nháp xuất ra vẫn có 29 ảnh chưa duyệt còn cảnh báo ngữ nghĩa (`07_error_list_v3`).
5. *Nhầm lớp bị che bởi box cùng lớp lân cận:* `img_0045` (lỗi số 3 ở đoạn dưới): box person chồng một phần lên dự đoán làm máy chẩn đoán sai (LOOSE_BOX thay vì WRONG_CLASS) và hạ điểm ưu tiên xuống hạng 92. Quy tắc "nhãn cùng lớp đã phủ vật này thì không cờ nhầm lớp" tránh báo động giả nhưng tạo điểm mù này.

**Ba lỗi tôi tự nhìn thấy khi xem `viz_labels.py`, đối chiếu với máy (`02_error_list_v1`, `05_review_queue`):**
1. `img_0001`: một người không được gán nhãn (thiếu box). Máy **bắt được**: `POSSIBLE_MISSING` (model thấy person, conf 0,95); ảnh hạng 25/125 trong hàng đợi, được duyệt.
2. `img_0020`: xe buýt bị gán `truck` (dòng 1, id 2). Máy **bắt được**: `POSSIBLE_WRONG_CLASS` (model thấy bus, conf 0,95); ảnh hạng 1/125, được duyệt.
3. `img_0045`: một người phụ nữ bị gán `car` (dòng 6, id 0). Máy **bắt hụt**: không báo `POSSIBLE_WRONG_CLASS` mà chỉ báo `POSSIBLE_LOOSE_BOX` (IoU 0,33). Lý do: dự đoán person (conf 0,75, IoU 0,91 với box car) còn chồng một phần (IoU 0,33 ≥ `iou_missing` 0,3) với box person ở dòng 1, nên bị coi là "đã có nhãn cùng lớp" và chỉ xét box lỏng, không xét nhầm lớp. Ảnh hạng 92/125 > ngân sách 80 nên **không ai duyệt**, lỗi còn nguyên trong bản nháp.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy.** Phần train Colab là tùy chọn, chấm riêng và chưa được thực hiện. Bản `clean_v1` hiện là bản nháp (Hold), nếu train sau này phải ghi rõ điều đó và so sánh chênh lệch với độ lệch giữa các seed trước khi kết luận.

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối: HOLD, không phát hành `clean_v1`.** Không đổi `warn_ratio_hold`, ngân sách duyệt hay ngưỡng để ép Release. Muốn thành Release cần giảm số ảnh còn cảnh báo từ 38 xuống ≤ 20 (10% của 202 = 20,2), tức xử lý thêm **tối thiểu 18 ảnh** trong 45 ảnh chưa duyệt (cả 38/38 ảnh còn cảnh báo đều nằm trong hàng đợi), tương ứng ngân sách duyệt ≥ 98 ảnh thay vì 80; hoặc nâng chất lượng checker (đặc biệt LOOSE_BOX, FALSE_POS) để giảm cảnh báo giả.

**(b) Ghi chú AI** (có dùng AI để viết 4 module `label_format`, `gate`, `autofix`, `second_opinion`):
- *Prompt chính:* yêu cầu ngắn "dựng pipeline" theo `GUIDE.md` Bước 2 (không phải prompt 4 ý đầy đủ); docstring và test của từng stub được dùng làm đặc tả.
- *Cách kiểm:* `pytest` 79/79; thêm ca ngoài test (một dòng dính 2 lỗi, dòng trống giữa file, ảnh có nhiều dự đoán, chạy `autofix` lần 2 không đổi gì); quét tĩnh bằng `check_submission.py`; chạy pipeline vào thư mục tạm trước khi chạy thật.
- *Một lần AI sai:* TODO(học viên): ghi 1 chỗ AI viết sai/thiếu và bạn đã sửa thế nào (nếu chưa có thì đọc kỹ code rồi tự tìm một chỗ thật).
