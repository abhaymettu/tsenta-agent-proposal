"""openclaw/scan-host.py: only regular files are read; specials never block or get followed; anything unread is
UNVERIFIED; hits across chunk boundaries are found; the canary never appears in argv or output. Hard timeouts throughout."""
import errno, importlib.util, io, os, shutil, socket, stat, subprocess, sys, tempfile, time, unittest
from unittest import mock

SCANNER = os.path.join(os.path.dirname(__file__), '..', 'openclaw', 'scan-host.py')
FAKE = 'sk-ant-canary-' + 'ab' * 24  # test-only fake
spec = importlib.util.spec_from_file_location('scan_host', SCANNER)
scan_host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan_host)
FIELDS = scan_host.FIELDS


def scan(*args, canary=FAKE, timeout=20):
    p = subprocess.run([sys.executable, '-I', SCANNER, *args], input=(canary + '\n').encode(), capture_output=True, timeout=timeout)
    rows = {}
    for line in p.stdout.decode().splitlines():
        f = line.split('\t')
        n = 2 + len(FIELDS)
        if len(f) >= n:
            row = dict(zip(('mode',) + FIELDS, [f[1]] + [int(x) for x in f[2:n]]), sample=f[n] if len(f) > n else '')
            rows[f[0]] = rows[os.path.realpath(f[0])] = row
    return p, rows


class ScanHost(unittest.TestCase):
    def setUp(self):
        self.d = os.path.realpath(tempfile.mkdtemp())  # macOS temp dirs sit behind the /var symlink; roots print as realpaths

    def tearDown(self):
        for root, dirs, _ in os.walk(self.d):
            for x in dirs:
                os.chmod(os.path.join(root, x), 0o700)
        shutil.rmtree(self.d, ignore_errors=True)

    def put(self, name, data):
        p = os.path.join(self.d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)
        return p

    def test_clean_tree_is_fully_read(self):
        self.put('a.txt', b'nothing'); self.put('sub/b.bin', os.urandom(5000))
        p, rows = scan('--full', self.d)
        self.assertEqual(p.returncode, 0)
        self.assertEqual((rows[self.d]['hits'], rows[self.d]['files_read']), (0, 2))

    def test_hit_is_found_and_canary_never_echoed(self):
        self.put('x/leak.log', b'prefix ' + FAKE.encode() + b' suffix')
        p, rows = scan('--full', self.d)
        self.assertEqual((p.returncode, rows[self.d]['hits']), (1, 1))
        self.assertIn('leak.log', rows[self.d]['sample'])
        self.assertNotIn(FAKE, p.stdout.decode() + p.stderr.decode())

    def test_cross_chunk_hit(self):
        data = b'x' * 1000 + FAKE.encode() + b'y' * 1000
        self.put('c.bin', data)
        for chunk in (7, 1000 + 5, 1000 + len(FAKE) - 1):  # boundaries inside the canary
            with self.subTest(chunk=chunk):
                p, rows = scan('--full', self.d, '--chunk', str(chunk))
                self.assertEqual(rows[self.d]['hits'], 1)

    def test_fifo_never_blocks_and_is_not_read(self):
        os.mkfifo(os.path.join(self.d, 'pipe'))  # no writer: any open-for-read without O_NONBLOCK, or a read, would hang
        t = time.monotonic()
        p, rows = scan('--full', self.d, timeout=10)
        self.assertLess(time.monotonic() - t, 8)
        self.assertEqual((rows[self.d]['fifo'], rows[self.d]['files_read'], p.returncode), (1, 0, 0))

    def test_socket_is_counted_not_read(self):
        s = socket.socket(socket.AF_UNIX)
        path = os.path.join(self.d, 's.sock')
        try:
            s.bind(path)
        except OSError:
            self.skipTest('AF_UNIX path too long here')
        try:
            p, rows = scan('--full', self.d, timeout=10)
            self.assertEqual((rows[self.d]['socket'], rows[self.d]['files_read']), (1, 0))
        finally:
            s.close()

    def test_symlink_is_not_followed(self):
        target = os.path.realpath(tempfile.mkdtemp())
        try:
            with open(os.path.join(target, 'secret'), 'wb') as f:
                f.write(FAKE.encode())
            os.symlink(os.path.join(target, 'secret'), os.path.join(self.d, 'link-to-file'))
            os.symlink(target, os.path.join(self.d, 'link-to-dir'))
            p, rows = scan('--full', self.d)
            self.assertEqual((rows[self.d]['hits'], rows[self.d]['symlink'], p.returncode), (0, 2, 0))
        finally:
            shutil.rmtree(target)

    def test_denied_is_unverified(self):
        if os.geteuid() == 0:
            self.skipTest('root reads everything')
        f = self.put('locked.txt', FAKE.encode()); os.chmod(f, 0)
        os.makedirs(os.path.join(self.d, 'lockeddir')); os.chmod(os.path.join(self.d, 'lockeddir'), 0)
        p, rows = scan('--full', self.d)
        self.assertEqual((rows[self.d]['denied'], rows[self.d]['hits'], p.returncode), (2, 0, 2))
        self.assertIn('locked', rows[self.d]['sample'])
        os.chmod(f, 0o600)

    def test_oversize_is_unverified(self):
        self.put('big.bin', b'z' * 5000 + FAKE.encode())
        p, rows = scan('--full', self.d, '--max-bytes', '1000')
        self.assertEqual((rows[self.d]['oversize'], rows[self.d]['hits'], p.returncode), (1, 0, 2))

    def test_root_timeout_is_unverified(self):
        for i in range(50):
            self.put(f'f{i}', b'q' * 100)
        p, rows = scan('--full', self.d, '--root-timeout', '0')
        self.assertEqual((rows[self.d]['timeout'], p.returncode), (1, 2))

    def test_recent_mode_reads_only_files_changed_after_the_stamp(self):
        self.put('old.log', FAKE.encode())  # ctime before the stamp: skipped (the real canary cannot be older than it)
        time.sleep(1.1)
        stamp = self.put('stamp', b'')
        time.sleep(1.1)
        self.put('new.log', b'fresh, clean')
        p, rows = scan('--stamp', stamp, '--recent', self.d)
        self.assertEqual((rows[self.d]['skipped_old'], rows[self.d]['files_read'], rows[self.d]['hits']), (1, 2, 0))
        self.put('newer.log', FAKE.encode())
        p, rows = scan('--stamp', stamp, '--recent', self.d)
        self.assertEqual(rows[self.d]['hits'], 1)

    def test_canary_not_in_argv(self):
        q = subprocess.Popen([sys.executable, '-I', SCANNER, '--full', self.d], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            argv = subprocess.run(['ps', '-o', 'command=', '-p', str(q.pid)], capture_output=True, text=True, timeout=10).stdout
            self.assertNotIn(FAKE, argv)
        finally:
            q.communicate((FAKE + '\n').encode(), timeout=10)

    def test_identity_change_is_unverified_not_clean(self):
        self.put('f.txt', b'clean'); os.makedirs(os.path.join(self.d, 'sub'))
        real = os.fstat

        def swapped(fd):  # simulate a path swapped between lstat and open: same type, different inode
            st = list(real(fd)); st[1] += 1
            return os.stat_result(st)
        for kind in ('file', 'dir'):
            with self.subTest(kind=kind):
                def fake(fd, kind=kind):
                    st = real(fd)
                    hit = stat.S_ISREG(st.st_mode) if kind == 'file' else (stat.S_ISDIR(st.st_mode) and st.st_ino != os.stat(self.d).st_ino)
                    return swapped(fd) if hit else st
                with mock.patch.object(scan_host.os, 'fstat', fake):
                    r, unv, hits, gone = scan_host.scan_root(self.d, FAKE.encode(), None, 1 << 20, 1 << 28, 30)
                self.assertEqual(r['changed'], 1, unv)
                self.assertTrue(any('changed' in u for u in unv))
                self.assertEqual(r['device'], 0)

    def test_vanished_entry_is_counted_not_unverified(self):
        self.put('kept.txt', b'clean'); self.put('gone.txt', b'clean'); os.makedirs(os.path.join(self.d, 'gonedir'))
        real_lstat, real_open = os.lstat, os.open

        def lstat(path, *a, **k):  # listed by scandir, removed before its lstat
            if path == 'gone.txt':
                raise FileNotFoundError(errno.ENOENT, 'gone')
            return real_lstat(path, *a, **k)

        def open_(path, flags, *a, **k):  # a listed subdir removed before its dir-open
            if str(path).endswith('gonedir'):
                raise FileNotFoundError(errno.ENOENT, 'gone')
            return real_open(path, flags, *a, **k)
        with mock.patch.object(scan_host.os, 'lstat', lstat), mock.patch.object(scan_host.os, 'open', open_):
            r, unv, hits, gone = scan_host.scan_root(self.d, FAKE.encode(), None, 1 << 20, 1 << 28, 30)
        self.assertEqual((r['vanished'], r['denied'], r['files_read']), (2, 0, 1))
        self.assertEqual(unv, [])
        self.assertTrue(any('gone.txt (vanished)' in g for g in gone))

    def test_missing_root_stays_denied(self):
        p, rows = scan('--full', os.path.join(self.d, 'nope'))
        self.assertEqual(p.returncode, 2)
        self.assertIn('root', p.stdout.decode())

    def test_name_hit_counts_and_path_is_redacted(self):
        self.put(FAKE + '.txt', b'clean contents')
        self.put('dir-' + FAKE + '/inner.log', b'x ' + FAKE.encode())
        p, rows = scan('--full', self.d)
        out = p.stdout.decode() + p.stderr.decode()
        self.assertEqual(p.returncode, 1)
        self.assertEqual((rows[self.d]['name_hits'], rows[self.d]['hits']), (2, 1))
        self.assertNotIn(FAKE, out)
        self.assertIn('<REDACTED-CANARY>', out)

    def test_root_prints_as_realpath(self):
        link = os.path.join(os.path.realpath(tempfile.mkdtemp()), 'link')
        try:
            os.symlink(self.d, link)
            p, _ = scan('--full', link)
            self.assertEqual(p.stdout.decode().split('\t')[0], self.d)
        finally:
            shutil.rmtree(os.path.dirname(link))

    def test_positive_control_and_missing_canary(self):
        p = subprocess.run([sys.executable, '-I', SCANNER, '--control'], input=(FAKE + '\n').encode(), capture_output=True, timeout=10)
        self.assertEqual(p.stdout.decode().strip(), 'control hits 1')
        p = subprocess.run([sys.executable, '-I', SCANNER, '--full', self.d], input=b'\n', capture_output=True, timeout=10)
        self.assertNotEqual(p.returncode, 0)


if __name__ == '__main__':
    unittest.main()
