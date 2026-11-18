"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    c = cfg["second_opinion"]
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    n_classes = len(ds.classes)
    issues = []
    for img in ds.image_files():
        stem = img.stem
        lines = ds.read_label_lines(stem)                  # giữ số dòng gốc; None = chưa có file nhãn
        size = ds.image_size(stem)
        if lines is None or stem not in preds or size is None:
            continue                                       # không có nhãn / không có dự đoán / ảnh hỏng: check khác báo
        W, H = size

        labels = []                                        # (số dòng gốc, id lớp, box) — chỉ dòng hợp lệ
        for no, text in lines:
            try:
                cls, *box = parse_yolo_line(text)
            except ValueError:
                continue
            if 0 <= cls < n_classes:
                labels.append((no, cls, tuple(box)))

        def add(code, msg, line=None, **extra):
            issues.append(Issue("second_opinion", WARN, code, stem, msg, line, extra))

        # Dự đoán đủ tin cậy và đủ lớn -> so với từng nhãn. Mỗi dự đoán sinh tối đa MỘT issue.
        for pc, conf, *pbox in (r for r in preds[stem] if r[1] >= c["conf"] and r[4] * W * r[5] * H >= c["min_area_px"]):
            pc = int(pc)
            cands = [(iou_xywh(pbox, b), cls) for _, cls, b in labels if iou_xywh(pbox, b) >= c["iou_missing"]]
            if not cands:
                add("POSSIBLE_MISSING", f"model thấy {_name(ds, pc)} (conf {conf:.2f}) nhưng nhãn không có box", conf=conf)
                continue
            same = [v for v, cls in cands if cls == pc]
            if same:
                if max(same) < c["iou_loose"]:
                    add("POSSIBLE_LOOSE_BOX", f"box {_name(ds, pc)} lỏng/lệch (IoU {max(same):.2f} < {c['iou_loose']})", conf=conf, iou=round(max(same), 4))
            elif max(v for v, _ in cands) >= c["iou_match"]:   # IoU trong [iou_missing, iou_match) mà khác lớp: mơ hồ, không cờ
                add("POSSIBLE_WRONG_CLASS", f"model cho là {_name(ds, pc)} (conf {conf:.2f}), nhãn gán lớp khác", conf=conf)

        # Nhãn không khớp vật nào model thấy (ngưỡng conf riêng `fp_conf`, không lọc diện tích).
        seen = [r[2:6] for r in preds[stem] if r[1] >= c["fp_conf"]]
        for no, cls, box in labels:
            best = max((iou_xywh(box, s) for s in seen), default=0.0)
            if best < c["iou_missing"]:
                add("POSSIBLE_FALSE_POS", f"box {_name(ds, cls)} không khớp vật nào model thấy (IoU lớn nhất {best:.2f})", no, iou=round(best, 4))
    return issues


def _name(ds, cls):
    return ds.classes[cls] if 0 <= cls < len(ds.classes) else str(cls)
