import peruopen


def test_version_is_defined() -> None:
    assert isinstance(peruopen.__version__, str)
