import os
import tempfile

from src.filesystem import LocalFileSystem, FileInfo, get_filesystem


class TestLocalFileSystem:

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write(self, path, content):
        with open(path, "w") as f:
            f.write(content)

    def test_ls_returns_file_infos(self):
        self._write(os.path.join(self.tmpdir, "a.txt"), "aaa")
        self._write(os.path.join(self.tmpdir, "b.txt"), "bbb")
        fs = LocalFileSystem()
        entries = fs.ls(self.tmpdir)
        names = {e.name for e in entries}
        assert "a.txt" in names
        assert "b.txt" in names
        for e in entries:
            assert isinstance(e, FileInfo)
            assert e.size == 3

    def test_ls_empty_dir(self):
        fs = LocalFileSystem()
        entries = fs.ls(self.tmpdir)
        assert entries == []

    def test_head(self):
        path = os.path.join(self.tmpdir, "data.txt")
        self._write(path, "hello world")
        fs = LocalFileSystem()
        assert fs.head(path, 5) == b"hello"
        assert fs.head(path, 100) == b"hello world"

    def test_mkdirs_creates_dirs(self):
        nested = os.path.join(self.tmpdir, "a", "b", "c")
        fs = LocalFileSystem()
        fs.mkdirs(nested)
        assert os.path.isdir(nested)

    def test_mkdirs_idempotent(self):
        fs = LocalFileSystem()
        fs.mkdirs(self.tmpdir)

    def test_mv(self):
        src = os.path.join(self.tmpdir, "src.txt")
        dst = os.path.join(self.tmpdir, "sub", "dst.txt")
        self._write(src, "moveme")
        fs = LocalFileSystem()
        fs.mkdirs(os.path.dirname(dst))
        fs.mv(src, dst)
        assert not os.path.exists(src)
        assert os.path.exists(dst)

    def test_md5(self):
        path = os.path.join(self.tmpdir, "hash.txt")
        self._write(path, "hello")
        fs = LocalFileSystem()
        expected = "5d41402abc4b2a76b9719d911017c592"
        assert fs.md5(path) == expected

    def test_md5_large_file(self):
        path = os.path.join(self.tmpdir, "large.txt")
        with open(path, "wb") as f:
            f.write(b"x" * 70000)
        fs = LocalFileSystem()
        digest = fs.md5(path)
        assert isinstance(digest, str)
        assert len(digest) == 32

    def test_get_filesystem_local(self):
        fs = get_filesystem()
        assert isinstance(fs, LocalFileSystem)

    def test_file_info_dataclass(self):
        info = FileInfo(name="f.txt", path="/a/f.txt", size=42)
        assert info.name == "f.txt"
        assert info.path == "/a/f.txt"
        assert info.size == 42
