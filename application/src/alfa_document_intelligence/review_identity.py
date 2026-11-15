"""Resolve the local account for review events."""

def local_review_actor() -> str:
    """Resolve the local process account without accepting an identity from a request."""
    import os
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            size = wintypes.DWORD(257)
            buffer = ctypes.create_unicode_buffer(size.value)
            api = ctypes.WinDLL("advapi32", use_last_error=True).GetUserNameW
            api.argtypes = (wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
            api.restype = wintypes.BOOL
            if not api(buffer, ctypes.byref(size)):
                raise OSError(ctypes.get_last_error(), "GetUserNameW failed")
            actor = buffer.value
        else:
            import pwd
            actor = pwd.getpwuid(os.geteuid()).pw_name
    except (OSError, KeyError, AttributeError) as exc:
        raise OSError("local account unavailable") from exc
    if not actor or not actor.strip():
        raise OSError("local account unavailable")
    return actor
