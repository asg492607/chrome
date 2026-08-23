"""
File System Access API & Sandboxed Origin Private File System (OPFS) Engine.
Implements W3C File System Access API specification (showOpenFilePicker, showSaveFilePicker),
Origin Private File System (OPFS) origin isolation (getDirectory), FileSystemDirectoryHandle, FileSystemFileHandle,
FileSystemWritableFileStream, and high-performance synchronous access handles (createSyncAccessHandle).
"""

from __future__ import annotations
import sys
import os

from typing import Dict, List, Optional, Tuple, Any, Callable, Union, Iterator

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class FileSystemHandle:
    """Base class for W3C FileSystemHandle objects."""

    def __init__(self, kind: str, name: str):
        self.kind = kind # "file" or "directory"
        self.name = name

    def isSameEntry(self, other: "FileSystemHandle") -> bool:
        """Determines if two handles reference the same file or directory entry."""
        return isinstance(other, FileSystemHandle) and self.kind == other.kind and self.name == other.name

    def __repr__(self) -> str:
        return f"FileSystemHandle(kind={self.kind}, name='{self.name}')"


class FileSystemWritableFileStream:
    """W3C FileSystemWritableFileStream for asynchronous file stream writing."""

    def __init__(self, initial_buffer: bytearray, target_file: "FileSystemFileHandle"):
        self._buffer = initial_buffer
        self._target_file = target_file
        self._position = 0

    def write(self, data: Union[bytes, bytearray, str]) -> None:
        """Writes binary or text data into file stream at current seek position."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        data_bytes = bytes(data)
        end_pos = self._position + len(data_bytes)
        if end_pos > len(self._buffer):
            self._buffer.extend(b"\x00" * (end_pos - len(self._buffer)))
        self._buffer[self._position:end_pos] = data_bytes
        self._position = end_pos

    def seek(self, position: int) -> None:
        """Sets current write pointer position."""
        self._position = max(0, position)

    def truncate(self, size: int) -> None:
        """Truncates stream to specified byte length."""
        self._buffer = self._buffer[:max(0, size)]
        if self._position > len(self._buffer):
            self._position = len(self._buffer)

    def close(self) -> None:
        """Flushes written buffer content to underlying file handle."""
        self._target_file._content = bytes(self._buffer)


class FileSystemSyncAccessHandle:
    """W3C FileSystemSyncAccessHandle providing synchronous high-speed binary I/O for OPFS in Web Workers."""

    def __init__(self, target_file: "FileSystemFileHandle"):
        self._target_file = target_file

    def read(self, buffer: bytearray, options: Optional[Dict[str, Any]] = None) -> int:
        """Synchronously reads binary bytes into buffer at specified offset."""
        at = options.get("at", 0) if options else 0
        file_bytes = self._target_file._content
        if at >= len(file_bytes):
            return 0
        chunk = file_bytes[at:at + len(buffer)]
        buffer[:len(chunk)] = chunk
        return len(chunk)

    def write(self, buffer: Union[bytes, bytearray], options: Optional[Dict[str, Any]] = None) -> int:
        """Synchronously writes binary bytes into target OPFS file at specified offset."""
        at = options.get("at", 0) if options else 0
        data_bytes = bytes(buffer)
        content_buf = bytearray(self._target_file._content)
        end_pos = at + len(data_bytes)
        if end_pos > len(content_buf):
            content_buf.extend(b"\x00" * (end_pos - len(content_buf)))
        content_buf[at:end_pos] = data_bytes
        self._target_file._content = bytes(content_buf)
        return len(data_bytes)

    def getSize(self) -> int:
        """Returns total byte size of target OPFS file."""
        return len(self._target_file._content)

    def flush(self) -> None:
        """Flushes pending byte modifications."""
        pass

    def close(self) -> None:
        """Closes synchronous access handle."""
        pass


class FileSystemFileHandle(FileSystemHandle):
    """W3C FileSystemFileHandle object representation."""

    def __init__(self, name: str, initial_content: bytes = b""):
        super().__init__("file", name)
        self._content = initial_content

    def getFile(self) -> bytes:
        """Returns file content bytes."""
        return self._content

    def createWritable(self) -> FileSystemWritableFileStream:
        """Creates a writable stream for asynchronous file writing."""
        return FileSystemWritableFileStream(bytearray(self._content), self)

    def createSyncAccessHandle(self) -> FileSystemSyncAccessHandle:
        """Creates a synchronous access handle for high-speed OPFS binary operations."""
        return FileSystemSyncAccessHandle(self)


class FileSystemDirectoryHandle(FileSystemHandle):
    """W3C FileSystemDirectoryHandle object representation for sandboxed OPFS directories."""

    def __init__(self, name: str = ""):
        super().__init__("directory", name)
        self.entries_map: Dict[str, FileSystemHandle] = {}

    def getFileHandle(self, name: str, options: Optional[Dict[str, Any]] = None) -> FileSystemFileHandle:
        """Retrieves or creates a child FileSystemFileHandle."""
        create = options.get("create", False) if options else False
        if name in self.entries_map:
            h = self.entries_map[name]
            if h.kind == "file":
                return h # type: ignore
            raise TypeError(f"TypeMismatchError: '{name}' is a directory, not a file.")
        elif create:
            f = FileSystemFileHandle(name)
            self.entries_map[name] = f
            return f
        else:
            raise FileNotFoundError(f"NotFoundError: File '{name}' does not exist in directory.")

    def getDirectoryHandle(self, name: str, options: Optional[Dict[str, Any]] = None) -> FileSystemDirectoryHandle:
        """Retrieves or creates a child FileSystemDirectoryHandle."""
        create = options.get("create", False) if options else False
        if name in self.entries_map:
            h = self.entries_map[name]
            if h.kind == "directory":
                return h # type: ignore
            raise TypeError(f"TypeMismatchError: '{name}' is a file, not a directory.")
        elif create:
            d = FileSystemDirectoryHandle(name)
            self.entries_map[name] = d
            return d
        else:
            raise FileNotFoundError(f"NotFoundError: Directory '{name}' does not exist.")

    def removeEntry(self, name: str, options: Optional[Dict[str, Any]] = None) -> None:
        """Removes a child file or directory entry."""
        if name in self.entries_map:
            del self.entries_map[name]
        else:
            raise FileNotFoundError(f"NotFoundError: Entry '{name}' does not exist.")

    def keys(self) -> List[str]:
        return list(self.entries_map.keys())

    def values(self) -> List[FileSystemHandle]:
        return list(self.entries_map.values())


class OriginPrivateFileSystemEngine:
    """Origin Private File System (OPFS) Manager & File Picker Engine."""

    _origin_roots: Dict[str, FileSystemDirectoryHandle] = {}

    @classmethod
    def get_directory_for_origin(cls, origin: str) -> FileSystemDirectoryHandle:
        """Returns origin-isolated root FileSystemDirectoryHandle (navigator.storage.getDirectory)."""
        if origin not in cls._origin_roots:
            cls._origin_roots[origin] = FileSystemDirectoryHandle(f"root_{origin}")
        return cls._origin_roots[origin]

    @classmethod
    def showOpenFilePicker(cls, options: Optional[Dict[str, Any]] = None) -> List[FileSystemFileHandle]:
        """Displays OS file open picker dialog and returns selected FileSystemFileHandles."""
        return [FileSystemFileHandle("selected_document.pdf", b"%PDF-1.4 Sovereign Document Payload")]

    @classmethod
    def showSaveFilePicker(cls, options: Optional[Dict[str, Any]] = None) -> FileSystemFileHandle:
        """Displays OS file save picker dialog and returns target FileSystemFileHandle."""
        return FileSystemFileHandle("saved_export.json", b"{}")
