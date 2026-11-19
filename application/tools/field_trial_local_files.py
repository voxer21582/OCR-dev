"""Windows-only, fail-closed reading of files inside an authorised local root.

The caller must send the bytes read from this handle directly to the next
stage; reopening a path loses the guarantee. Errors must not expose paths.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import os
from pathlib import Path


@contextmanager
def open_local_file(root, path):
    """Open one ordinary, singly-linked file while pinning all parent folders."""
    if os.name != 'nt':
        raise ValueError('unsupported platform')
    import ctypes
    import msvcrt
    from ctypes import wintypes
    from alfa_document_intelligence.__main__ import _lock_plain_windows_directory

    stack = ExitStack()
    try:
        root, path = Path(root), Path(path)
        if not root.is_absolute() or not path.is_absolute() or '..' in root.parts or '..' in path.parts:
            raise ValueError('invalid path')
        root_name, path_name = os.path.abspath(root), os.path.abspath(path)
        if root_name.startswith(('\\\\', '//')) or path_name.startswith(('\\\\', '//')) or ':' in path_name[2:]:
            raise ValueError('nonlocal path')
        if os.path.normcase(os.path.commonpath((root_name, path_name))) != os.path.normcase(root_name) or os.path.normcase(root_name) == os.path.normcase(path_name):
            raise ValueError('outside root')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        drive_type = kernel.GetDriveTypeW
        drive_type.argtypes = [wintypes.LPCWSTR]
        drive_type.restype = wintypes.UINT
        if drive_type(os.path.splitdrive(root_name)[0] + '\\') != 3:
            raise ValueError('nonlocal drive')
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        info = kernel.GetFileInformationByHandleEx
        info.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        info.restype = wintypes.BOOL
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        file_type = kernel.GetFileType
        file_type.argtypes = [wintypes.HANDLE]
        file_type.restype = wintypes.DWORD

        class AttributeTag(ctypes.Structure):
            _fields_ = [('attributes', wintypes.DWORD), ('tag', wintypes.DWORD)]

        parent = Path(path_name).parent
        for directory in reversed((parent, *parent.parents)):
            stack.enter_context(_lock_plain_windows_directory(str(directory)))
        handle = create(path_name, 0x80000000, 0x1, None, 3, 0x00200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ValueError('file unavailable')
        fd = None
        try:
            attributes = AttributeTag()
            if (not info(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes))
                    or attributes.attributes & (0x400 | 0x10) or file_type(handle) != 1):
                raise ValueError('invalid file')
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            handle = None  # fd now owns the Windows handle
            stream = stack.enter_context(os.fdopen(fd, 'rb'))
            fd = None  # stream now owns fd
            if os.fstat(stream.fileno()).st_nlink != 1:
                raise ValueError('linked file')
        finally:
            if fd is not None:
                os.close(fd)
            if handle is not None:
                close(handle)
    except Exception:
        stack.close()
        raise ValueError('local file unavailable') from None
    with stack:
        yield stream
