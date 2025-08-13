def test_import():
    import osint
    assert hasattr(osint, "__version__")
