"""Turn Printer-MIB alert codes into plain-language messages (English, Thai, Japanese).

Printers report problems in the standard prtAlertTable (RFC 3805) as numeric
codes such as 808 = "input media supply empty". This module maps them to a
short title, an action for whoever walks up to the printer, and a severity:

    critical  the printer cannot print until someone acts
    warning   needs attention soon
    info      not a problem (e.g. sleep mode)
"""

LANGS = ("en", "th", "ja")

COLORS = {
    "black":   {"en": "Black",   "th": "ดำ",     "ja": "ブラック"},
    "cyan":    {"en": "Cyan",    "th": "ฟ้า",     "ja": "シアン"},
    "magenta": {"en": "Magenta", "th": "ชมพู",    "ja": "マゼンタ"},
    "yellow":  {"en": "Yellow",  "th": "เหลือง",  "ja": "イエロー"},
}
NO_COLOR = {"en": "Toner", "th": "", "ja": ""}

# code -> (kind, severity, {lang: (title, action)}). {tray} and {color} are filled per alert.
ALERT_CODES = {
    3: ("cover_open", "critical", {
        "en": ("A cover is open", "Close the printer cover"),
        "th": ("ฝาเครื่องเปิดอยู่", "ปิดฝาเครื่องให้สนิท"),
        "ja": ("カバーが開いています", "プリンターのカバーをしっかり閉じてください")}),
    5: ("cover_open", "critical", {
        "en": ("A cover or interlock is open", "Close the printer cover"),
        "th": ("ฝาเครื่องเปิดอยู่", "ปิดฝาเครื่องให้สนิท"),
        "ja": ("カバーが開いています", "プリンターのカバーをしっかり閉じてください")}),
    8: ("paper_jam", "critical", {
        "en": ("Paper jam", "Open the printer and remove the jammed paper"),
        "th": ("กระดาษติด", "เปิดเครื่องแล้วดึงกระดาษที่ติดออก"),
        "ja": ("紙詰まり", "プリンターを開けて詰まった用紙を取り除いてください")}),
    10: ("part_life", "warning", {
        "en": ("A part is near end of life", "Plan a service visit or spare part"),
        "th": ("ชิ้นส่วนใกล้หมดอายุ", "แจ้งช่างหรือเตรียมอะไหล่"),
        "ja": ("部品の寿命が近づいています", "保守の手配・予備部品の準備をしてください")}),
    11: ("part_life", "critical", {
        "en": ("A part has reached end of life", "Call service to replace the part"),
        "th": ("ชิ้นส่วนหมดอายุ", "เรียกช่างเปลี่ยนชิ้นส่วน"),
        "ja": ("部品の寿命が切れました", "保守を呼んで部品を交換してください")}),
    504: ("sleep", "info", {
        "en": ("Sleep / energy-save mode", ""),
        "th": ("อยู่ในโหมดประหยัดพลังงาน", ""),
        "ja": ("スリープ（省エネ）モード", "")}),
    801: ("tray_missing", "warning", {
        "en": ("Tray {tray} is missing or open", "Push tray {tray} back in"),
        "th": ("ถาด {tray} ไม่ได้ใส่เข้าที่", "ดันถาด {tray} กลับเข้าที่"),
        "ja": ("トレイ{tray}が正しくセットされていません", "トレイ{tray}を奥まで差し込んでください")}),
    807: ("paper_low", "warning", {
        "en": ("Tray {tray} paper is low", "Refill tray {tray} soon"),
        "th": ("ถาด {tray} กระดาษใกล้หมด", "เตรียมเติมกระดาษถาด {tray}"),
        "ja": ("トレイ{tray}の用紙が残りわずかです", "トレイ{tray}の用紙補充を準備してください")}),
    808: ("paper_empty", "warning", {
        "en": ("Tray {tray} is out of paper", "Load paper into tray {tray}"),
        "th": ("ถาด {tray} กระดาษหมด", "เติมกระดาษถาด {tray}"),
        "ja": ("トレイ{tray}の用紙切れ", "トレイ{tray}に用紙を補充してください")}),
    902: ("output_full", "warning", {
        "en": ("Output tray almost full", "Empty the output tray"),
        "th": ("ถาดรับกระดาษใกล้เต็ม", "หยิบกระดาษออกจากถาดรับ"),
        "ja": ("排紙トレイがほぼ満杯です", "排紙トレイから用紙を取り出してください")}),
    903: ("output_full", "critical", {
        "en": ("Output tray is full", "Empty the output tray"),
        "th": ("ถาดรับกระดาษเต็ม", "หยิบกระดาษออกจากถาดรับ"),
        "ja": ("排紙トレイが満杯です", "排紙トレイから用紙を取り出してください")}),
    1101: ("toner_empty", "critical", {
        "en": ("{color} toner is empty", "Replace the {color} toner"),
        "th": ("หมึก{color}หมด", "เปลี่ยนตลับหมึก{color}"),
        "ja": ("{color}トナー切れ", "{color}トナーを交換してください")}),
    1104: ("toner_low", "warning", {
        "en": ("{color} toner is nearly empty", "Get a spare {color} toner ready"),
        "th": ("หมึก{color}ใกล้หมด", "เตรียมตลับหมึก{color}สำรอง"),
        "ja": ("{color}トナーが残りわずかです", "{color}トナーの予備を用意してください")}),
    1106: ("waste_toner", "warning", {
        "en": ("Waste toner box almost full", "Get a new waste toner box ready"),
        "th": ("กล่องหมึกเสียใกล้เต็ม", "เตรียมกล่องหมึกเสียใบใหม่"),
        "ja": ("廃トナーボックスがほぼ満杯です", "新しい廃トナーボックスを用意してください")}),
    1107: ("waste_toner", "critical", {
        "en": ("Waste toner box is full", "Replace the waste toner box"),
        "th": ("กล่องหมึกเสียเต็ม", "เปลี่ยนกล่องหมึกเสีย"),
        "ja": ("廃トナーボックスが満杯です", "廃トナーボックスを交換してください")}),
}

UNKNOWN_ACTION = {"en": "Check the printer's control panel",
                  "th": "ตรวจสอบที่หน้าจอเครื่องพิมพ์",
                  "ja": "プリンターの操作パネルを確認してください"}

# Conclusions the printer never states itself, added by summarize().
SYNTHETIC = {
    "offline": {
        "en": ("Printer is not responding (off or unplugged)", "Check power and the network cable"),
        "th": ("เครื่องไม่ตอบสนอง (ปิดอยู่ หรือสายแลนหลุด)", "ตรวจว่าเครื่องเปิดอยู่และสายแลนเสียบแน่น"),
        "ja": ("プリンターが応答しません（電源オフまたはLAN未接続）", "電源とLANケーブルを確認してください")},
    "paper_all_empty": {
        "en": ("Every tray is out of paper - cannot print", "Load paper into at least one tray"),
        "th": ("กระดาษหมดทุกถาด เครื่องพิมพ์งานไม่ได้", "เติมกระดาษอย่างน้อย 1 ถาด"),
        "ja": ("全トレイ用紙切れ - 印刷できません", "少なくとも1つのトレイに用紙を補充してください")},
}
HEADLINE_OK = {"en": "OK", "th": "ปกติ", "ja": "正常"}
HEADLINE_MORE = {"en": " (+{n} more)", "th": " และอีก {n} เรื่อง", "ja": "（他{n}件）"}

SEVERITY_RANK = {"critical": 2, "warning": 1, "info": 0}


def _color_of(text):
    t = (text or "").lower()
    for key, names in COLORS.items():
        if key in t:
            return names
    return NO_COLOR


def explain(code, severity_level=None, group_index=None, description=""):
    """One prtAlertTable row -> dict with kind, severity, and title/action per language.
    Unknown codes fall back to the printer's own text and severity, so nothing is hidden."""
    tray = str(group_index) if isinstance(group_index, int) and group_index > 0 else "?"
    color = _color_of(description)
    entry = ALERT_CODES.get(code)
    if entry:
        kind, severity, texts = entry
    else:
        kind = "other"
        # prtAlertSeverityLevel: 3 critical, 4 warning, 5 warningBinaryChangeEvent
        severity = "critical" if severity_level == 3 else "warning" if severity_level in (4, 5) else "info"
        own = (description or f"code {code}").strip()
        texts = {lang: (own, UNKNOWN_ACTION[lang]) for lang in LANGS}
    out = {"code": code, "kind": kind, "severity": severity,
           "tray": int(tray) if tray.isdigit() else None,
           "text": (description or "").strip(), "title": {}, "action": {}}
    for lang in LANGS:
        title, action = texts[lang]
        fill = {"tray": tray, "color": color[lang]}
        out["title"][lang] = title.format(**fill).strip()
        out["action"][lang] = action.format(**fill).strip()
    return out


def synthetic(kind):
    texts = SYNTHETIC[kind]
    return {"code": None, "kind": kind, "severity": "critical", "tray": None, "text": "",
            "title": {lang: texts[lang][0] for lang in LANGS},
            "action": {lang: texts[lang][1] for lang in LANGS}}


def summarize(online, alerts, trays):
    """-> (sorted alerts incl. synthetic ones, attention summary with a one-line headline per language)."""
    extra = []
    paper_trays = [t for t in trays if not t["manualFeed"] and t["state"] != "unknown"]
    if online and paper_trays and all(t["state"] == "empty" for t in paper_trays):
        extra.append(synthetic("paper_all_empty"))
    if not online:
        extra.append(synthetic("offline"))
    ordered = sorted(extra + alerts, key=lambda a: -SEVERITY_RANK[a["severity"]])
    problems = [a for a in ordered if a["severity"] != "info"]
    level = ("critical" if any(a["severity"] == "critical" for a in problems)
             else "warning" if problems else "ok")
    if problems:
        more = len(problems) - 1
        headline = {lang: problems[0]["title"][lang] + (HEADLINE_MORE[lang].format(n=more) if more else "")
                    for lang in LANGS}
    else:
        headline = dict(HEADLINE_OK)
    return ordered, {
        "level": level,
        "critical": sum(a["severity"] == "critical" for a in problems),
        "warning": sum(a["severity"] == "warning" for a in problems),
        "headline": headline,
    }
