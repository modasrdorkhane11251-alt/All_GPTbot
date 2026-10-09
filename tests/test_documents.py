from app.documents import extract
def test_text(): assert extract("a.txt",b"hello")=="hello"
def test_bad_type():
    try: extract("a.exe",b"x")
    except ValueError: return
    assert False
