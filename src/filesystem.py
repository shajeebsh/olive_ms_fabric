from __future__ import annotations

import hashlib
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class FileInfo:
    name: str
    path: str
    size: int


class FileSystem(ABC):

    @abstractmethod
    def ls(self, path: str) -> List[FileInfo]:
        ...

    @abstractmethod
    def head(self, path: str, max_bytes: int) -> bytes:
        ...

    @abstractmethod
    def mkdirs(self, path: str) -> None:
        ...

    @abstractmethod
    def mv(self, src: str, dst: str) -> None:
        ...

    @abstractmethod
    def md5(self, path: str) -> str:
        ...


class FabricFileSystem(FileSystem):

    def ls(self, path: str) -> List[FileInfo]:
        from mssparkutils import fs
        return [FileInfo(f.name, f.path, f.size) for f in fs.ls(path)]

    def head(self, path: str, max_bytes: int) -> bytes:
        from mssparkutils import fs
        result = fs.head(path, max_bytes)
        if isinstance(result, str):
            return result.encode("utf-8")
        return result

    def mkdirs(self, path: str) -> None:
        from mssparkutils import fs
        fs.mkdirs(path)

    def mv(self, src: str, dst: str) -> None:
        from mssparkutils import fs
        fs.mv(src, dst)

    def md5(self, path: str) -> str:
        raw = self.head(path, 10 * 1024 * 1024)
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        return hashlib.md5(data).hexdigest()


class LocalFileSystem(FileSystem):

    def ls(self, path: str) -> List[FileInfo]:
        entries = []
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if os.path.isfile(full):
                entries.append(FileInfo(name, full, os.path.getsize(full)))
        return entries

    def head(self, path: str, max_bytes: int) -> bytes:
        with open(path, "rb") as f:
            return f.read(max_bytes)

    def mkdirs(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def mv(self, src: str, dst: str) -> None:
        shutil.move(src, dst)

    def md5(self, path: str) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()


def get_filesystem() -> FileSystem:
    try:
        from mssparkutils import fs
        fs.ls("/")
        return FabricFileSystem()
    except (ImportError, NameError):
        return LocalFileSystem()
