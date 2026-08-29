from types import SimpleNamespace

import pandas as pd
from ktem.index.file.ui import FileIndexPage


def _page_without_ui() -> FileIndexPage:
    page = object.__new__(FileIndexPage)
    page.selected_panel_false = "未选择文件"
    page.selected_panel_true = "已选文件：{name}"
    return page


def test_localized_file_table_selection_keeps_internal_id() -> None:
    page = _page_without_ui()
    table = pd.DataFrame([{"ID": "file-1", "文件名": "病历.pdf"}])
    event = SimpleNamespace(value="病历.pdf", index=(0, 1), selected=True)

    file_id, label = page.interact_file_list(table, event)

    assert file_id == "file-1"
    assert label == "已选文件：病历.pdf"


def test_group_selection_uses_untranslated_state_values() -> None:
    page = _page_without_ui()
    groups = [{"id": "group-1", "name": "心内科", "files": ["file-1"]}]
    event = SimpleNamespace(value="心内科", index=(0, 1), selected=True)

    result = page.interact_group_list(groups, event)

    assert result == ("### 分组信息", "group-1", "心内科", ["file-1"])
