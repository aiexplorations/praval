import praval


def test_version_exported():
    assert isinstance(praval.__version__, str)


def test_all_exports_present():
    for name in praval.__all__:
        assert hasattr(praval, name)
