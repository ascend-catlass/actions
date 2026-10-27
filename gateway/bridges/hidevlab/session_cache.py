"""Encrypted HTTP session cache: Windows DPAPI or Linux Fernet + private key."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import stat

MAGIC = b'HIDEVLAB-DPAPI-1\0'
FERNET_MAGIC = b'HIDEVLAB-FERNET-1\0'
IS_WINDOWS = os.name == 'nt'


class CacheError(Exception):
    pass


def default_path(account):
    key = hashlib.sha256(account.encode('utf-8')).hexdigest()[:20]
    if IS_WINDOWS:
        root = os.environ.get('LOCALAPPDATA')
        if not root:
            raise CacheError('LOCALAPPDATA is unavailable; use --no-cache')
        return Path(root) / 'HiDevLabHttp' / ('session-' + key + '.bin')
    root = Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local'/'state')
    if not root.is_absolute():
        raise CacheError('XDG_STATE_HOME must be absolute')
    return root / 'hidevlab-http' / ('session-' + key + '.bin')


def private_path(path, directory=False):
    """Refuse symlinks, foreign owners and group/world access on POSIX."""
    if os.name != 'posix':
        return
    metadata=Path(path).lstat()
    correct_type=stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    if not correct_type or metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode)&0o077:
        raise CacheError('Cache/key paths must be owned by the current user, with directory 0700 and file 0600 permissions')


def private_directory(path):
    path=Path(path)
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    private_path(path,directory=True)


def fernet_key(create=False):
    from cryptography.fernet import Fernet
    configured=os.environ.get('HIDEVLAB_CACHE_KEY')
    if configured:
        try:
            key=configured.encode('ascii')
            Fernet(key)
            return key
        except (ValueError,UnicodeError):
            raise CacheError('HIDEVLAB_CACHE_KEY is not a valid Fernet key') from None
    root=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')
    if not root.is_absolute():
        raise CacheError('XDG_CONFIG_HOME must be absolute')
    path=root/'hidevlab-http'/'cache.key'
    if create:
        private_directory(path.parent)
        try:
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor,'wb') as output:
                output.write(Fernet.generate_key())
                output.flush()
                os.fsync(output.fileno())
    private_path(path.parent,directory=True)
    private_path(path)
    key=path.read_bytes()
    try:
        Fernet(key)
    except ValueError:
        raise CacheError('Local cache encryption key is invalid') from None
    return key


def seal(data):
    if IS_WINDOWS:
        return MAGIC+crypt(data)
    from cryptography.fernet import Fernet
    return FERNET_MAGIC+Fernet(fernet_key(create=True)).encrypt(data)


def unseal(raw):
    if raw.startswith(MAGIC):
        if not IS_WINDOWS:
            raise CacheError('Windows DPAPI cache cannot be used on Linux; log in once on Linux')
        return crypt(raw[len(MAGIC):],decrypt=True)
    if raw.startswith(FERNET_MAGIC):
        from cryptography.fernet import Fernet, InvalidToken
        try:
            return Fernet(fernet_key()).decrypt(raw[len(FERNET_MAGIC):])
        except InvalidToken:
            raise CacheError('Session cache authentication failed') from None
    raise CacheError('Unrecognized encrypted session file')


def crypt(data, decrypt=False):
    if os.name != 'nt':
        raise CacheError('Encrypted cache currently requires Windows; use --no-cache')
    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
    source = ctypes.create_string_buffer(data)
    incoming = Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = Blob()
    api = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    protect = api.CryptProtectData
    unprotect = api.CryptUnprotectData
    protect.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    unprotect.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    protect.restype = unprotect.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    # UI_FORBIDDEN, without LOCAL_MACHINE: only the current Windows user can decrypt.
    ok = unprotect(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)) if decrypt else protect(ctypes.byref(incoming), 'HiDevLab HTTP session', None, None, None, 1, ctypes.byref(outgoing))
    if not ok:
        raise CacheError('Windows session encryption failed (error '+str(ctypes.get_last_error())+')')
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData)
    finally:
        kernel.LocalFree(ctypes.cast(outgoing.pbData, ctypes.c_void_p))


def save(path, account, session, csrf, created_at=None):
    now = time.time()
    cookies = []
    for cookie in session.cookies:
        if cookie.domain.lstrip('.') != 'huawei.com' and not cookie.domain.lstrip('.').endswith('.huawei.com'):
            continue
        cookies.append({key: getattr(cookie, key) for key in ('name','value','version','port','domain','path','secure','expires','discard','comment','comment_url','rfc2109')})
        cookies[-1]['rest'] = cookie._rest.copy()
    payload = {'version':1,'account':account,'created_at':created_at or now,'updated_at':now,'cookies':cookies,'csrf':csrf}
    encrypted = seal(json.dumps(payload,ensure_ascii=False).encode('utf-8'))
    path = Path(path)
    private_directory(path.parent)
    if path.exists() or path.is_symlink():
        private_path(path)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.session-',delete=False) as output:
            temp_path=Path(output.name)
            output.write(encrypted)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path,path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def load(path, account, session, max_age_hours=168):
    path=Path(path)
    private_path(path.parent,directory=True)
    private_path(path)
    raw = path.read_bytes()
    try:
        payload = json.loads(unseal(raw))
    except (ValueError, UnicodeError):
        raise CacheError('Invalid encrypted session contents') from None
    if payload.get('version') != 1 or payload.get('account') != account:
        raise CacheError('Session cache account or format mismatch')
    created_at = payload.get('created_at',0)
    if not isinstance(created_at,(int,float)) or time.time()-created_at > max_age_hours*3600 or created_at > time.time()+60:
        raise CacheError('Local session cache age limit reached')
    cookies=payload.get('cookies')
    if not isinstance(cookies,list):
        raise CacheError('Session cache cookie list is invalid')
    from requests.cookies import RequestsCookieJar, create_cookie
    jar=RequestsCookieJar()
    for entry in cookies:
        domain=entry.get('domain','').lstrip('.')
        if domain != 'huawei.com' and not domain.endswith('.huawei.com'):
            raise CacheError('Unexpected domain in session cache')
        jar.set_cookie(create_cookie(**entry))
    session.cookies=jar
    return payload.get('csrf'),created_at
