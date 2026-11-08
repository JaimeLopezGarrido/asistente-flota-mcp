from pathlib import Path


def test_estructura_basica():
    raiz = Path(__file__).resolve().parent.parent
    assert (raiz / "README.md").exists()
    assert not (raiz / ".env").exists() or ".env" in (raiz / ".gitignore").read_text()
