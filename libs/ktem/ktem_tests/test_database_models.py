from ktem.db.base_models import BaseConversation, BaseIssueReport, BaseSettings


def test_json_fields_do_not_share_mutable_defaults():
    conversation_a = BaseConversation()
    conversation_b = BaseConversation()
    setting_a = BaseSettings()
    setting_b = BaseSettings()
    issue_a = BaseIssueReport()
    issue_b = BaseIssueReport()

    conversation_a.data_source["file"] = "a.pdf"
    setting_a.setting["language"] = "zh"
    issue_a.issues["category"] = "model"

    assert conversation_b.data_source == {}
    assert setting_b.setting == {}
    assert issue_b.issues == {}
