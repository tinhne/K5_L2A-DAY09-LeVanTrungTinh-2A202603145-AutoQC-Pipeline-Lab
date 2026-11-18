# Báo cáo Day 09 — Lê Văn Trung Tính, 2A202603145

## 1. Kết luận trước

Pipeline kết luận **Hold** (chưa phát hành). Lô có 224 ảnh, sau khi loại ảnh xấu còn 202 ảnh, xuất ra `submission/export/clean_v1/` như một bản nháp. Không còn lỗi bắt buộc nào, nhưng còn 38/202 ảnh (18,8%) có cảnh báo mà chưa ai duyệt, cao hơn mức cho phép 10%. Số lỗi bắt buộc giảm dần: 36 lúc đầu, còn 6 sau khi máy tự sửa (đều là ảnh thiếu file nhãn), và 0 sau khi người duyệt.

## 2. Lỗi và phân việc

Số liệu lấy từ `02_error_list_v1`. Lô có 224 ảnh, sau cửa vào còn 202 ảnh. Tổng cộng 58 lỗi bắt buộc và 153 cảnh báo.

| Lỗi                                                                                                                                                        |     Số lượng | Ai sửa                              | Ghi chú                                           |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -----------: | ----------------------------------- | ------------------------------------------------- |
| Ảnh hỏng (CORRUPT_IMAGE 2), ảnh quá nhỏ (BAD_SIZE 3)                                                                                                       |    5/224 ảnh | Máy, loại ở cửa vào                 | Không dùng được nên bỏ                            |
| Ảnh trùng (DUP_IMAGE_EXACT 8, DUP_IMAGE_NEAR 4)                                                                                                            |   12/224 ảnh | Máy, loại                           | Giữ ảnh đầu, bỏ các ảnh trùng sau                 |
| Ảnh trùng với tập test (LEAK_TEST)                                                                                                                         |    5/224 ảnh | Máy, loại                           | Tránh điểm đo cao giả                             |
| Dòng nhãn hỏng (BAD_CLASS_ID 6, BAD_FORMAT 3, BOX_ZERO 4, DUP_BOX 7)                                                                                       |      20 dòng | Máy, xoá dòng (`drop_line`)         | Lỗi cú pháp, xoá an toàn                          |
| Box tràn ra ngoài ảnh (BOX_OUT_OF_IMAGE)                                                                                                                   |       8 dòng | Máy, cắt box (`clip_box`)           | Cắt về trong ảnh, giữ nguyên lớp                  |
| Tên lớp sai trong `data.yaml` (BAD_CLASS_NAME)                                                                                                             |        2 mục | Máy, ghi lại tên (`rename_classes`) | Chỉ cần sửa 1 lần                                 |
| Thiếu file nhãn (MISSING_LABEL_FILE)                                                                                                                       |    6/202 ảnh | **Người**                           | Máy không tự bịa nhãn, chỉ đánh dấu `needs_label` |
| Nghi ngờ về nghĩa: POSSIBLE_MISSING 53 (thiếu box), POSSIBLE_FALSE_POS 29 (box thừa), POSSIBLE_LOOSE_BOX 28 (box lỏng), POSSIBLE_WRONG_CLASS 18 (nhầm lớp) | 128 cảnh báo | **Người**                           | Model lớn chỉ nghi ngờ, có thể sai                |
| Cảnh báo khác: EMPTY_LABEL 12, BOX_TINY 6, CLASS_RARE 4, BOX_HUGE 3                                                                                        |  25 cảnh báo | **Người**                           | Cần người phán đoán                               |

Hàng đợi (`05_review_queue.csv`) có 125 ảnh. Ảnh có cảnh báo càng nặng thì điểm càng cao, ảnh thiếu file nhãn được cộng 10 điểm vì chỉ người mới gán được. Vì vậy `img_0020` đứng đầu (11,5 điểm), và 6 ảnh thiếu nhãn nằm trong 7 ảnh đầu. Ngân sách chỉ cho duyệt 80 ảnh, nên 45 ảnh cuối không ai xem. Trong 123 cảnh báo về nghĩa (nhầm lớp, thiếu box, box lỏng...) sau khi máy sửa, người xem được 94 (76%), còn 29 nằm ở ảnh chưa duyệt.

## 3. Calibration (2 ngưỡng)

Đo trên bộ `data/calib` (39 ảnh), kết quả đầy đủ ở `submission/calibration/calibration_report.md`. P là precision (cờ báo có đúng không), R là recall (bắt được bao nhiêu lỗi).

| Tham số                 | Lúc đầu | Chọn    | P / R (trước → sau)                                                                                                                | Vì sao chọn                                                                                                                                                                                                                            |
| ----------------------- | ------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `duplicates.phash_dist` | 2       | **12**  | Ảnh gần trùng: 1,00/0,50 → 1,00/0,67. Ảnh trùng hệt: 1,00/1,00, không đổi                                                          | Lỗi này làm máy tự loại ảnh, nên tôi ưu tiên precision (loại nhầm ảnh tốt là mất dữ liệu). Từ 4 đến 14 kết quả trên calib như nhau. Tôi chọn 12 vì trên raw nó bắt thêm 2 cặp ảnh trùng thật so với 4. Mức 16 bị loại, xem bên dưới    |
| `second_opinion.conf`   | 0.25    | **0.6** | Thiếu box: 0,50/1,00 → 0,57/1,00. Nhầm lớp: 0,56/0,83 → 0,62/0,83. Box lỏng: 0,29/0,40 → 0,20/0,20. Box thừa: 0,31/1,00, không đổi | Cảnh báo này gửi cho người xem nên ưu tiên recall. 0.6 là mức cao nhất mà recall của thiếu box vẫn là 1,00 (0.7 tụt còn 0,88, 0.8 tụt còn 0,75). Đổi lại box lỏng kém đi, tôi chấp nhận vì loại này kém ở mọi mức (F1 tối đa chỉ 0,46) |

Chạy thử trên raw bằng config tạm (không đổi `configs/`): bộ (2; 0.25) cho Hold 60/205 ảnh (29,3%), hàng đợi 145 ảnh. Bộ (12; 0.6) cho Hold 38/202 ảnh (18,8%), hàng đợi 125 ảnh. Nếu chọn `conf=0.8` thì gate ra Release 16/202 (7,9%), nhưng chỉ vì hàng đợi nhỏ lại còn 102 ảnh và máy bỏ sót 25% lỗi thiếu box. Đó là Release giả nên tôi không chọn. Cách chạy lại: chép `configs/pipeline.yaml` vào `work/`, đổi 2 giá trị, rồi chạy `python -m pipeline.run --config work/<file>.yaml --reports work/rX --export-dir work/eX --work work/wX`.

**Chỗ calibration có thể đánh lừa:** trên calib, `phash_dist=16` có F1 cao nhất (0,91 cho ảnh gần trùng) và precision vẫn 1,00. Nhưng calib chỉ có 6 ảnh gần trùng, bỏ sót một ảnh là recall nhảy 17%. Khi chạy trên raw, so với 12, mức 16 thêm 3 cặp ảnh gần trùng, cả 3 đều sát mép 16. Tôi mở xem thì 2/3 cặp là hai ảnh khác hẳn nhau (`img_0011` với `img_0008`: quần vợt và trượt tuyết; `img_0177` với `img_0113`: lướt sóng và chân dung). Chỉ `img_0084` với `img_0074` là trùng thật (cắt khung). Số ảnh bị gọi là rò rỉ test cũng nhảy từ 5 lên 11, nhưng tôi không mở ảnh test để kiểm vì luật cấm dùng `data/test` để chọn ngưỡng. Ngược lại ở mức 12, 2 cặp thêm (`img_0186` với `img_0061`, `img_0223` với `img_0077`) đều cùng một cảnh, chỉ bị cắt hoặc đổi sáng.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Cửa chặn có chặn thật.** Tôi chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên 6 ảnh thiếu nhãn còn nguyên). Kết quả: **Rework**, mã thoát 20, còn 6 lỗi bắt buộc (MISSING_LABEL_FILE), 112/202 ảnh (55,4%) còn cảnh báo, và thư mục `work/exp_nb/` không được tạo (không xuất dataset). Lần `make run` bình thường (ngân sách 80) ra Hold, mã thoát 10, xuất bản nháp.

**(b) Những gì pipeline không bắt được (có bằng chứng):**

1. Ảnh gần trùng bị biến đổi mạnh: ở mức 12, calib bỏ sót 2/6 ảnh (R = 0,67). Nới lên 16 thì bắt thêm nhưng gộp nhầm ảnh khác nhau (xem mục 3), nên không có ngưỡng nào vừa bắt đủ vừa an toàn.
2. Box lỏng: ở `conf=0.6`, box lỏng chỉ đạt P = 0,20 và R = 0,20 trên calib (bắt 1/5 lỗi). Máy gần như không phân biệt được box lệch nhẹ.
3. Báo động giả: box thừa chỉ có P = 0,31 (11 cảnh báo sai trên bộ calib nhãn người, do model và nhãn người lệch nhau tự nhiên). Ngược lại, máy không báo thiếu box cho vật nhỏ hơn `min_area_px` (600 px²), nên vật nhỏ bị bỏ sót mà không ai biết.
4. Ảnh chưa ai xem: 45 ảnh trong hàng đợi không được duyệt, nên bản nháp xuất ra vẫn có 29 ảnh chưa duyệt còn cảnh báo về nghĩa (`07_error_list_v3`).

**Ba lỗi tôi tự nhìn thấy khi xem ảnh bằng `viz_labels.py`, và máy có bắt được không:**

1. `img_0001`: một người không được gán nhãn (thiếu box). Máy **bắt được** (POSSIBLE_MISSING, model thấy người với conf 0,95). Ảnh đứng hạng 25/125 nên được duyệt.
2. `img_0020`: xe buýt bị gán là `truck` (dòng 1, id 2). Máy **bắt được** (POSSIBLE_WRONG_CLASS, model thấy bus với conf 0,95). Ảnh đứng hạng 1/125 nên được duyệt.
3. `img_0045`: một người phụ nữ bị gán là `car` (dòng 6, id 0). Máy **bắt hụt**: nó không báo nhầm lớp mà chỉ báo box lỏng (POSSIBLE_LOOSE_BOX, IoU 0,33). Lý do: dự đoán "person" của model (conf 0,75, IoU 0,91 với box car) còn chồng một phần (IoU 0,33) lên box person ở dòng 1. Máy coi như đã có nhãn cùng lớp phủ chỗ đó nên chỉ xét box lỏng, không xét nhầm lớp. Ảnh này đứng hạng 92/125, vượt ngân sách 80, nên không ai duyệt và lỗi còn nguyên trong bản nháp. Quy tắc này giúp tránh báo động giả nhưng tạo ra điểm mù này.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

Tôi train trên Google Colab (T4) bằng `scripts/train_compare.py`: model `yolo26n.pt`, 20 epoch, batch 16, imgsz 640, 3 seed (0, 1, 2) cho mỗi biến thể, cùng tập val (`gold_val`, 40 ảnh) và cùng tập test (100 ảnh). Kết quả ở `submission/results/`, tôi không sửa tay.

| Biến thể              | Ảnh train | mAP50         | mAP50-95      | precision     | recall        |
| --------------------- | --------: | ------------- | ------------- | ------------- | ------------- |
| raw                   |       224 | 0,720 ± 0,010 | 0,508 ± 0,007 | 0,742 ± 0,057 | 0,646 ± 0,021 |
| clean (bản nháp Hold) |       202 | 0,707 ± 0,021 | 0,492 ± 0,010 | 0,785 ± 0,045 | 0,617 ± 0,019 |

mAP50 của từng seed: raw 0,726 / 0,726 / 0,709, clean 0,718 / 0,683 / 0,721.

**Kết luận: chưa kết luận được.** Chênh mAP50 (clean trừ raw) là −0,013, nhỏ hơn độ lệch giữa các seed (0,010 ở raw, 0,021 ở clean). Riêng seed 1 của clean (0,683) đã thấp hơn hai seed còn lại của nó 0,035, lớn hơn cả mức chênh giữa hai biến thể. Nên tôi không thể nói dữ liệu sau pipeline tốt hơn hay kém hơn dữ liệu gốc. Chỉ nói được là với 3 seed và 100 ảnh test, tôi không đo thấy lợi ích. Precision của clean cao hơn (0,785 so với 0,742) và recall thấp hơn (0,617 so với 0,646), nhưng chênh cũng nhỏ so với độ lệch giữa seed nên chưa đủ chắc. Theo lớp: car, person, bus chênh không quá 0,006, riêng truck chênh nhiều nhất (raw 0,606, clean 0,553) nhưng truck dao động rất mạnh giữa các seed (raw từ 0,521 đến 0,657) và clean chỉ có 41 box truck, 32 box bus (`class_stats.csv`).

**Nguyên nhân có thể và cách kiểm:**

1. raw lẫn ảnh trùng và ảnh rò rỉ test. Pipeline loại 22/224 ảnh khỏi raw ở cửa vào (8 trùng hệt, 4 gần trùng, 5 rò rỉ test, 5 hỏng hoặc quá nhỏ). Có 5 ảnh raw giống ảnh test nên điểm của raw có thể bị cao giả. Cách kiểm: đo lại mô hình raw trên tập test sau khi bỏ các ảnh test bị trùng (danh sách ở cột `extra` của `01_intake.csv`).
2. clean chưa thật sự sạch. Đây là bản nháp Hold: 45/125 ảnh trong hàng đợi chưa ai duyệt, 29 ảnh chưa duyệt còn cảnh báo về nghĩa, và lỗi như `img_0045` (người gán là `car`) còn nguyên. Cách kiểm: train thêm biến thể `oracle` (nhãn người, làm mức chặn trên), hoặc duyệt hết hàng đợi rồi train lại clean.
3. Ít dữ liệu, lớp hiếm, test nhỏ. Chỉ 202 đến 224 ảnh train và 100 ảnh test, truck và bus có rất ít box, nên AP theo lớp dao động mạnh. Cách kiểm: tăng lên ít nhất 5 seed và xem độ lệch có nhỏ lại không.
4. clean ít hơn raw khoảng 10% ảnh (202 so với 224), nên lợi ích của việc sửa nhãn có thể bị mất đi vì thiếu dữ liệu. Cách kiểm: so với một biến thể chỉ loại ảnh trùng và rò rỉ mà không sửa nhãn.

Việc tiếp theo: tăng số seed, đo lại raw sau khi bỏ ảnh test bị trùng, chạy `oracle`, và duyệt nốt hàng đợi để có bản clean đúng nghĩa trước khi kết luận.

## 6. Quyết định và ghi chú AI

**(a) Quyết định cuối: Hold, không phát hành `clean_v1`.** Tôi không đổi mức 10%, ngân sách duyệt, hay chọn `conf` cao để ép ra Release. Muốn thành Release thì số ảnh còn cảnh báo phải giảm từ 38 xuống còn 20 trở xuống (10% của 202 là 20,2). Cần xử lý thêm ít nhất 18 ảnh trong 45 ảnh chưa duyệt (cả 38 ảnh còn cảnh báo đều nằm trong hàng đợi), tức ngân sách duyệt khoảng 98 ảnh thay vì 80. Cách khác là làm máy kiểm tốt hơn (nhất là box lỏng và box thừa) để ít cảnh báo giả hơn.

**(b) Ghi chú AI.** Tôi có dùng AI để viết 4 module `label_format`, `gate`, `autofix`, `second_opinion`.

- Prompt chính: tóm tắt nội dung bài lab, tập trung giải thích keypoint, mục đích, kiến thức có được từ bài lab. Checklist đầu việc cần làm. Phân tích 4 pipeline, chỗ tôi cần sửa, vì sao sửa, khác biệt ở đâu để so sánh đối chiếu kết quả trước và sau khi sửa pipeline.
- Cách kiểm: `pytest` xanh (79 test của lab). Thử thêm các ca ngoài test: một dòng dính 2 lỗi, dòng trống giữa file, ảnh có nhiều dự đoán, chạy `autofix` lần 2 không đổi gì. Chạy `check_submission.py`. Chạy thử pipeline vào thư mục tạm trước khi chạy thật.
- Một lần AI sai: hàm `fix` trong `autofix.py` do AI viết xoá dòng nhãn chỉ dựa vào số dòng trong issue, không kiểm lại nội dung dòng đó. Tôi đối chiếu docstring dòng 24 ("chạy lần 2 không làm gì thêm") với code rồi chạy `work/stale_demo.py`: gọi `fix` lần 2 với issue cũ thì mất thêm một dòng nhãn tốt, mà `label_format` sau đó vẫn báo 0 lỗi nên không ai biết. Luồng `run.py` không bị vì issue luôn được tính lại mỗi lần. Tôi sửa bằng cách kiểm lại lỗi trên từng dòng trước khi xoá (commit `58aa9a3`). Chạy lại thì lần 2 không đổi gì, còn `03_fixes.csv` của lần chạy thật giữ nguyên.
- Báo cáo này: Dùng AI giúp điền nhanh từ số liệu thật trong `submission/reports/`, `submission/calibration/` và `submission/results/`. Tôi đã đọc lại, đối chiếu số và xác nhận. Ba lỗi ở mục 4 là tôi tự xem ảnh và phát hiện. Tự train rồi giải nén và test, tự resaerch tìm lỗi sai của AI.
