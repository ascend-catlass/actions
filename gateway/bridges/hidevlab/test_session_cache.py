import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import requests
import session_cache
from hidevlab_http import APIError, Client


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'session.bin'
        environment=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(Path(self.tmp.name)/'config'),'HIDEVLAB_CACHE_KEY':''})
        environment.start()
        self.addCleanup(environment.stop)
        self.s=requests.Session()
        self.s.cookies.set('sessionId','TEST_SECRET_COOKIE',domain='.huawei.com',path='/',secure=True)
        self.s.cookies.set('CASTGC','DUPLICATE_A',domain='.id1.cloud.huawei.com',path='/CAS')
        self.s.cookies.set('CASTGC','DUPLICATE_B',domain='.id1.cloud.huawei.com',path='/')

    def test_encrypted_roundtrip_preserves_duplicate_cookie_paths(self):
        session_cache.save(self.path,'EXAMPLE',self.s,'TEST_CSRF')
        raw=self.path.read_bytes()
        self.assertNotIn(b'TEST_SECRET_COOKIE',raw)
        self.assertNotIn(b'TEST_CSRF',raw)
        restored=requests.Session()
        csrf,created=session_cache.load(self.path,'EXAMPLE',restored)
        self.assertEqual(csrf,'TEST_CSRF')
        self.assertEqual(len(restored.cookies),3)
        self.assertGreater(created,0)
        self.assertTrue(restored.cookies.get('sessionId',domain='.huawei.com',path='/')=='TEST_SECRET_COOKIE')

    def test_reject_wrong_account(self):
        session_cache.save(self.path,'EXAMPLE',self.s,None)
        with self.assertRaises(session_cache.CacheError):
            session_cache.load(self.path,'DIFFERENT',requests.Session())

    def test_reject_expired_cache(self):
        session_cache.save(self.path,'EXAMPLE',self.s,None,time.time()-3600*200)
        with self.assertRaises(session_cache.CacheError):
            session_cache.load(self.path,'EXAMPLE',requests.Session(),168)

    def test_reject_tampered_ciphertext(self):
        session_cache.save(self.path,'EXAMPLE',self.s,None)
        raw=bytearray(self.path.read_bytes())
        raw[-15]^=1
        self.path.write_bytes(raw)
        with self.assertRaises(session_cache.CacheError):
            session_cache.load(self.path,'EXAMPLE',requests.Session())

    def test_server_expiry_falls_back_to_login(self):
        session_cache.save(self.path,'EXAMPLE',self.s,None)
        client=Client()
        with patch.object(client,'verify_identity',side_effect=APIError('/hwaccount/getUserInfo',401)):
            self.assertFalse(client.resume_cache('EXAMPLE',self.path))
        self.assertFalse(client.s.cookies)

    def test_network_failure_does_not_trigger_fresh_login(self):
        session_cache.save(self.path,'EXAMPLE',self.s,None)
        client=Client()
        with patch.object(client,'verify_identity',side_effect=requests.Timeout):
            with self.assertRaises(requests.Timeout):
                client.resume_cache('EXAMPLE',self.path)


class LinuxProviderTests(CacheTests):
    def setUp(self):
        super().setUp()
        provider=patch.object(session_cache,'IS_WINDOWS',False)
        provider.start()
        self.addCleanup(provider.stop)

    def test_wrong_key_cannot_decrypt(self):
        from cryptography.fernet import Fernet
        session_cache.save(self.path,'EXAMPLE',self.s,None)
        with patch.dict(os.environ,{'HIDEVLAB_CACHE_KEY':Fernet.generate_key().decode('ascii')}):
            with self.assertRaises(session_cache.CacheError):
                session_cache.load(self.path,'EXAMPLE',requests.Session())

    @unittest.skipUnless(os.name=='posix','POSIX permission check requires Linux/Unix')
    def test_refuse_group_readable_cache(self):
        session_cache.save(self.path,'EXAMPLE',self.s,None)
        self.path.chmod(0o644)
        with self.assertRaises(session_cache.CacheError):
            session_cache.load(self.path,'EXAMPLE',requests.Session())

    @unittest.skipUnless(os.name=='posix','POSIX permission check requires Linux/Unix')
    def test_cache_and_key_permissions(self):
        import stat
        session_cache.save(self.path,'EXAMPLE',self.s,None)
        key=Path(os.environ['XDG_CONFIG_HOME'])/'hidevlab-http'/'cache.key'
        self.assertEqual(stat.S_IMODE(key.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(key.parent.stat().st_mode),0o700)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)

    @unittest.skipUnless(os.name=='posix','POSIX permission check requires Linux/Unix')
    def test_refuse_symlink_key(self):
        session_cache.save(self.path,'EXAMPLE',self.s,None)
        key=Path(os.environ['XDG_CONFIG_HOME'])/'hidevlab-http'/'cache.key'
        target=key.with_name('real.key')
        key.rename(target)
        key.symlink_to(target)
        with self.assertRaises(session_cache.CacheError):
            session_cache.load(self.path,'EXAMPLE',requests.Session())


if __name__=='__main__':
    unittest.main()
