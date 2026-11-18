"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    p = cfg["label_format"]
    n_classes = len(ds.classes)
    issues = []
    for lf in ds.label_files():
        stem = lf.stem
        size = ds.image_size(stem)                 # None nếu không có ảnh / ảnh hỏng -> bỏ qua BOX_TINY
        kept = []                                  # (id lớp, box) các dòng đã qua 3 kiểm tra bắt buộc, để dò DUP_BOX

        def add(sev, code, msg, line, **extra):
            issues.append(Issue("label_format", sev, code, stem, msg, line, extra))

        for no, text in ds.read_label_lines(stem) or []:          # `no` = số dòng GỐC (dòng trống vẫn được đếm)
            try:
                cls, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", f"dòng nhãn sai định dạng: {e}", no)
                continue
            if not 0 <= cls < n_classes:
                add(ERROR, "BAD_CLASS_ID", f"id lớp {cls} ngoài 0..{n_classes - 1}", no)
                continue
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", f"box không có diện tích (w={w}, h={h})", no)
                continue

            # từ đây dòng đã hợp lệ về cú pháp: các kiểm tra sau độc lập nhau, một dòng có thể dính nhiều lỗi
            box = (cx, cy, w, h)
            overflow = max(0.0, w / 2 - cx, cx + w / 2 - 1, h / 2 - cy, cy + h / 2 - 1)   # mức tràn lớn nhất trong 4 mép
            if overflow > p["overflow_tol"]:
                add(ERROR, "BOX_OUT_OF_IMAGE", f"box tràn ảnh {overflow:.4f}", no, overflow=round(overflow, 6))
            dup = next((j for j, (c, b) in kept if c == cls and iou_xywh(b, box) > p["dup_box_iou"]), None)
            if dup is not None:
                add(ERROR, "DUP_BOX", f"trùng box ở dòng {dup} (cùng lớp, IoU > {p['dup_box_iou']})", no, of_line=dup)
            kept.append((no, (cls, box)))
            if size is not None:
                short_px = min(w * size[0], h * size[1])
                if short_px < p["min_box_px"]:
                    add(WARN, "BOX_TINY", f"box quá nhỏ: cạnh ngắn {short_px:.1f}px < {p['min_box_px']}px", no, px=round(short_px, 2))
            if w * h > p["max_box_frac"]:
                add(WARN, "BOX_HUGE", f"box chiếm {w * h:.0%} diện tích ảnh", no, frac=round(w * h, 4))
    return issues
