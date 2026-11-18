# Báo cáo Day 09 — Lê Văn Trung Tính, 2A202603145

## 1. Kết luận

Sau khi chạy toàn bộ pipeline, mình kết luận **Hold** và chưa phát hành bộ `clean_v1`.

Lô đầu vào có 224 ảnh. Pipeline loại 22 ảnh ở cửa intake (ảnh hỏng/quá nhỏ, ảnh trùng, hoặc trùng với tập test), nên còn 202 ảnh được xuất thành bản nháp trong `submission/export/clean_v1/`. Kết quả không còn lỗi bắt buộc, nhưng trong 202 ảnh vẫn có 38 ảnh (18,8%) còn cảnh báo chưa được người duyệt. Ngưỡng dự án là 10% nên bản này chưa đạt.

## 2. Lỗi và cách xử lý

Số liệu được lấy từ `submission/reports/02_error_list_v1.txt`.

| Nhóm lỗi | Số lượng | Xử lý |
|---|---:|---|
| Ảnh hỏng hoặc kích thước quá nhỏ | 5/224 | Pipeline loại ở bước intake |
| Ảnh trùng hệt hoặc gần trùng | 12/224 | Giữ một ảnh đại diện, loại các ảnh trùng |
| Trùng với tập test | 5/224 | Loại để tránh điểm đo bị rò rỉ |
| Lỗi định dạng nhãn, class ID, box rỗng, box trùng | 20 dòng | Pipeline xoá dòng hoặc giữ lại nội dung hợp lệ |
| Box tràn ra ngoài ảnh | 8 dòng | Cắt box về trong khung ảnh |
| Tên lớp trong `data.yaml` sai | 2 mục | Pipeline cập nhật lại theo danh sách lớp |
| Thiếu file nhãn | 6/202 | Không tự tạo nhãn; đánh dấu `needs_label` để người gán |
| Cảnh báo nghi ngờ: thiếu box, box thừa, box lỏng, nhầm lớp | 128 | Để người xem lại vì model có thể đoán sai |
| Cảnh báo khác: box nhỏ/lớn, label trống, lớp hiếm | 25 | Để người xem lại |

Pipeline tự sửa được phần lỗi cú pháp và loại được ảnh không dùng được. Lỗi cần hiểu ý nghĩa ảnh vẫn chuyển sang hàng đợi duyệt. Có 125 ảnh trong `05_review_queue.csv`; hàng đợi được xếp theo trọng số cảnh báo, thiếu nhãn có điểm cao nhất. Ngân sách là 80 ảnh, nên 45 ảnh cuối không được duyệt.

Trong 123 cảnh báo về nghĩa sau khi pipeline sửa, 94 cảnh báo nằm trong nhóm đã được duyệt (76%), còn 29 cảnh báo nằm ở ảnh chưa xem.

## 3. Chọn hai ngưỡng calibration

Mình dùng bộ calib 39 ảnh để đánh giá hai thông số cần calibrate:

| Thông số | Giá trị đầu | Giá trị mình chọn | Kết quả trên calib | Lý do |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | 2 | **12** | Phát hiện ảnh gần trùng: P/R trước 1,00/0,50; sau 1,00/0,67 | Ưu tiên không loại nhầm ảnh tốt. Mức 12 bắt được thêm ảnh trùng thật so với mức thấp hơn mà precision vẫn giữ 1,00 |
| `second_opinion.conf` | 0,25 | **0,6** | Thiếu box: 0,57/1,00; nhầm lớp: 0,62/0,83 | Giữ recall của lỗi thiếu box ở mức cao nhất mà mình chọn được. Đây là cảnh báo đưa cho người xem, nên ưu tiên bắt đủ lỗi hơn là giảm bớt cảnh báo giả |

Hai bộ tham số khi thử trên dữ liệu raw cho kết quả khác biệt rõ:

- `(2; 0,25)`: 60/205 ảnh còn cảnh báo, Hold, hàng đợi 145 ảnh.
- `(12; 0,6)`: 38/202 ảnh còn cảnh báo, Hold, hàng đợi 125 ảnh.

Mình cũng thử `conf=0,8` để xem có ép được Release không. Kết quả Release là 16/202 ảnh cảnh báo (7,9%), nhưng recall của lỗi thiếu box giảm còn 0,75. Mình không chọn vì nhìn bảng kết quả vẫn không an toàn.

Một điểm calibration dễ gây hiểu nhầm là `phash_dist=16` cho kết quả gần trùng trên calib khá cao: P/R/F1 là 1,00/0,83/0,91. Tuy nhiên calib chỉ có 6 ảnh gần trùng, nên bỏ sót một ảnh đã làm recall thay đổi mạnh. Khi chạy trên raw, mức 16 còn loại thêm 3 cặp ảnh so với mức 12; hai cặp trong số đó không phải ảnh trùng (một cặp quần vợt/trượt tuyết, một cặp lướt sóng/chân dung). Chỉ một cặp là trùng thật, kiểu một ảnh cắt khung của ảnh kia. Vì vậy mình không chọn mức 16 chỉ vì F1 trên calib trông cao hơn.

## 4. Cổng chặn và các lỗi pipeline chưa bắt được

Mình đã chạy pipeline với `--budget 0`. Khi không có người duyệt, kết quả là **Rework**, exit code 20, còn 6 lỗi thiếu file nhãn và 112/202 ảnh (55,4%) có cảnh báo. Pipeline không tạo thư mục export. Khi chạy ngân sách 80 bình thường, kết quả là Hold, exit code 10 và xuất bản nháp `clean_v1`.

Sau khi đối chiếu báo cáo và xem một số ảnh bằng `scripts/viz_labels.py`, mình thấy còn ba giới hạn đáng lưu ý:

1. Ảnh gần trùng biến đổi mạnh vẫn có thể không bắt được. Mức 12 bỏ sót 2/6 ảnh gần trùng trong calib, recall chỉ 0,67.
2. Box lỏng khó phân biệt với model. Với `conf=0,6`, loại lỗi này có P/R trên calib là 0,20/0,20, tức bắt đúng 1/5 lỗi.
3. Có thể xảy ra báo động sai hoặc bỏ sót. Box thừa có precision chỉ 0,31 trên calib. Ngược lại, model bỏ qua dự đoán có diện tích dưới `min_area_px=600`, nên vật nhỏ có thể không được cảnh báo.

Ba ảnh mình đã tự xem thấy:

- `img_0001`: một người không được gán nhãn. Model bắt được cảnh báo `POSSIBLE_MISSING` với confidence 0,95 và ảnh này nằm trong ngân sách nên đã được xem.
- `img_0020`: xe buýt được gán nhầm thành `truck`. Model bắt được `POSSIBLE_WRONG_CLASS` với confidence 0,95 và ảnh nằm hạng cao trong hàng đợi.
- `img_0045`: một người phụ nữ bị gán là `car`. Model thấy `person` với confidence 0,75 và box dự đoán có IoU 0,91 với box nhãn. Tuy nhiên phần chồng sang box người khác cũng tạo ra IoU 0,33, nên pipeline chỉ báo `POSSIBLE_LOOSE_BOX` và không báo nhầm lớp. Ảnh nằm ngoài 80 ảnh được duyệt, nên lỗi còn trong bản Hold.

## 5. So sánh train raw và clean

Mình train bằng notebook trên Google Colab với GPU T4: YOLO26n, 20 epoch, batch 16, ảnh kích thước 640, ba seed (0, 1, 2). Tập val và test giữ nguyên; chỉ so sánh dữ liệu train raw và clean.

| Biến thể | Số ảnh train | mAP50 | mAP50-95 | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| raw | 224 | 0,720 ± 0,010 | 0,508 ± 0,007 | 0,742 ± 0,057 | 0,646 ± 0,021 |
| clean | 202 | 0,707 ± 0,021 | 0,492 ± 0,010 | 0,785 ± 0,045 | 0,617 ± 0,019 |

Chênh mAP50 clean trừ raw là −0,013. Trong ba seed của raw, mAP50 là 0,726 / 0,726 / 0,709; của clean là 0,718 / 0,683 / 0,721. Độ dao động của clean cao hơn mức chênh, và seed 1 của clean thấp bất thường nên mình chưa kết luận clean tốt hơn hay xấu hơn.

Từ kết quả hiện tại, mình chỉ có thể nói rằng với dữ liệu nhỏ, 3 seed và 100 ảnh test, pipeline chưa cho thấy lợi ích rõ ràng.

Một số nguyên nhân có thể:

1. Bộ raw có thể chứa ảnh trùng và ảnh rò rỉ test, nên kết quả ban đầu có thể bị cao giả.
2. `clean_v1` vẫn là bản Hold, chưa duyệt hết 45 ảnh trong hàng đợi; còn 29 cảnh báo về nghĩa ở ảnh chưa xem.
3. Lô dữ liệu train/test nhỏ; kết quả theo lớp dao động. Riêng truck có 41 box trong tập train clean và AP dao động mạnh.
4. Clean giảm còn 202 ảnh, giảm khoảng 10% so với raw, nên có thể mất đi dữ liệu dù nhãn đã được sửa.

Trước khi kết luận thật sự, cần train nhiều seed hơn, đo lại raw sau khi bỏ ảnh trùng test và chạy thêm biến thể oracle hoặc duyệt hết hàng đợi rồi train lại.

## 6. Quyết định và ghi chú về AI

Mình giữ quyết định **Hold**. Mình không đổi ngưỡng cảnh báo 10%, không tăng ngân sách duyệt hơn 80 ảnh trong bài chạy chính, và không hạ `conf` chỉ để ép pipeline ra Release.

Để bản này chuyển thành Release, số ảnh còn cảnh báo phải giảm từ 38 xuống còn không quá 20 (10% của 202). Vì cả 38 ảnh này đều nằm trong hàng đợi, ngân sách duyệt cần tăng ít nhất lên khoảng 98 ảnh. Cách khác là cải thiện phần nhận diện cảnh báo của model để giảm báo sai, nhất là box lỏng và box thừa.

Trong quá trình làm bài, mình dùng AI chủ yếu để hỗ trợ nháp code, debug và đối chiếu tài liệu. Sau khi nhận kết quả từ AI, mình vẫn đọc lại logic, chạy test và kiểm bằng dữ liệu ngoài test mẫu.

- Mình hỏi AI theo hướng cụ thể: tóm tắt nội dung lab, checklist cần làm, logic bốn module và cách hai module khác nhau để đối chiếu kết quả trước/sau.
- Mình đã chạy 79 test của lab, thêm ba ca ngoài test (dòng dính nhiều lỗi, dòng trống giữa file, ảnh có nhiều dự đoán), chạy pipeline trên thư mục tạm, rồi chạy `scripts/check_submission.py`.
- AI từng viết hàm `fix()` trong `autofix.py` chỉ xoá dòng theo số thứ tự trong issue cũ, không kiểm lại dòng hiện tại. Mình phát hiện bằng trường hợp chạy autofix lần hai: code có thể xoá nhầm một dòng nhãn tốt dù dữ liệu mới không còn lỗi. Sau đó mình sửa hàm `_still_applies()` để kiểm lại nội dung dòng trước khi sửa và commit `58aa9a3`; chạy lại cho kết quả idempotent.

Ngoài ra, ba mẫu lỗi ở mục 4 là mình tự mở ảnh và kiểm. Phần train, calibration và kết quả export đều chạy lại bằng lệnh trong repo; mình đối chiếu số trong các file báo cáo trước khi ghi vào phần tổng kết.
