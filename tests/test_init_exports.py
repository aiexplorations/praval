from importlib.metadata import version

import praval


def test_version_exported():
    assert praval.__version__ == version("praval")


def test_all_exports_present():
    for name in praval.__all__:
        assert hasattr(praval, name)
