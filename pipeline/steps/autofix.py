"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_CODES = {"CORRUPT_IMAGE", "BAD_SIZE", "LEAK_TEST"}          # cộng thêm mọi mã DUP_IMAGE_*


def _is_remove(code):
    return code in REMOVE_CODES or code.startswith("DUP_IMAGE_")


def _clip(text):
    """Cắt box về trong [0,1]. Trả về dòng mới, hoặc None nếu sau khi cắt box không còn diện tích (hoặc dòng không đọc được)."""
    try:
        cls, cx, cy, w, h = parse_yolo_line(text)
    except ValueError:
        return None
    x1, x2 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    y1, y2 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    nw, nh = round(x2 - x1, 6), round(y2 - y1, 6)
    if nw <= 0 or nh <= 0:
        return None
    return f"{cls} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {nw:.6f} {nh:.6f}"


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]            # cảnh báo là việc của người: không đụng tới
    fixes = []

    def record(image, line, action, before, after):
        fixes.append({"image": image, "line": line, "action": action, "before": before, "after": after})

    # 1) Xoá ảnh (+ nhãn). Làm trước: mọi issue theo dòng của ảnh đã xoá sẽ bị bỏ qua êm.
    removed = set()
    for stem in sorted({i.image for i in errors if _is_remove(i.code)}):
        img, lab = ds.image_path(stem), ds.label_path(stem)
        if img is None and not lab.exists():
            continue                                               # đã xoá từ trước
        name = img.name if img else f"{stem} (chỉ còn nhãn)"
        if img is not None:
            img.unlink()
        lab.unlink(missing_ok=True)
        removed.add(stem)
        record(stem, None, "remove_image", name, "(đã xoá ảnh + nhãn)")

    # 2) Sửa theo dòng: gom theo file rồi ghi MỘT lần, vì số dòng trong issue là số dòng GỐC.
    by_file = defaultdict(lambda: defaultdict(set))                # stem -> số dòng -> các mã lỗi
    for i in errors:
        if i.image not in removed and i.line is not None and (i.code in DROP_CODES or i.code == "BOX_OUT_OF_IMAGE"):
            by_file[i.image][i.line].add(i.code)
    for stem in sorted(by_file):
        path = ds.label_path(stem)
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()   # giữ cả dòng trống để số dòng không lệch
        out, changed = list(raw), False
        drop = set()
        for no in sorted(by_file[stem]):
            if no > len(raw):
                continue                                           # số dòng cũ không còn tồn tại
            text = raw[no - 1]
            if by_file[stem][no] & DROP_CODES:                     # dòng dính nhiều lỗi: xoá thắng, chỉ ghi một fix
                drop.add(no)
                record(stem, no, "drop_line", text.strip(), "(đã xoá dòng)")
                continue
            new = _clip(text)
            if new is None:
                drop.add(no)
                record(stem, no, "drop_line", text.strip(), "(đã xoá dòng: box nằm ngoài ảnh hoặc không đọc được)")
            else:
                out[no - 1] = new
                record(stem, no, "clip_box", text.strip(), new)
            changed = True
        if drop:
            out = [t for n, t in enumerate(out, 1) if n not in drop]
            changed = True
        if changed:
            path.write_text("".join(t + "\n" for t in out), encoding="utf-8")

    # 3) Ảnh chưa có file nhãn: máy không bịa nhãn (cũng không tạo file rỗng), chuyển cho người.
    for stem in sorted({i.image for i in errors if i.code == "MISSING_LABEL_FILE"} - removed):
        if not ds.label_path(stem).exists():
            record(stem, None, "needs_label", "(không có file)", "chuyển người gán")

    # 4) data.yaml: ghi lại `names` đúng danh sách lớp của dự án (giữ nguyên các khoá khác, giữ kiểu dict/list).
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        want = list(cfg["classes"])
        data = {}
        if ds.yaml_path.exists():
            try:
                data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                data = {}
        if not isinstance(data, dict):
            data = {}
        old = data.get("names")
        if old != want and old != dict(enumerate(want)):
            data["names"] = dict(enumerate(want)) if isinstance(old, dict) else want
            ds.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
            show = lambda n: ", ".join(map(str, n.values() if isinstance(n, dict) else n)) if n else "(không có)"
            record("data.yaml", None, "rename_classes", show(old), show(want))
    return fixes
