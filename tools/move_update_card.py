"""把三張更新卡片搬到通知群組（_init_notify 開頭）。"""
from pathlib import Path

p = Path("app/ui/settings_page.py")
lines = p.read_text("utf-8").splitlines()
# 檔案行 573-601（1-based）：updateCheckCard + updateNotifyCard + updateOnStartCard
start = 572  # 0-based
end = 601    # exclusive（檔案行 602 是空行）
block = lines[start:end]
assert "updateCheckCard = PushSettingCard" in block[0], block[0]
assert "updateOnStartCard" in "\n".join(block), "block mismatch"
del lines[start:end]
# _init_notify 的 group 建立後插入
anchor = '        notify = SettingCardGroup(t("settings.group.notify"), self)\n        self._groups.append(notify)\n'
text = "\n".join(lines) + "\n"
assert anchor in text, "notify anchor not found"
insert = anchor + "\n" + "\n".join("        " + b.lstrip() if False else b for b in []) + ""
# 重建縮排：block 原本就是 8 空格縮排，直接用
insert_block = "\n".join(block)
text = text.replace(anchor, anchor + "\n" + insert_block + "\n")
p.write_text(text, "utf-8")
print("moved 3 update cards to notify group")
