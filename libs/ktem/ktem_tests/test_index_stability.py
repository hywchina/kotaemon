from ktem.index.file.pipelines import _run_embedding_in_background


def test_hospital_indexing_keeps_embedding_errors_in_request():
    assert not _run_embedding_in_background(True, hospital_mode=True)
    assert _run_embedding_in_background(True, hospital_mode=False)
    assert not _run_embedding_in_background(False, hospital_mode=False)
