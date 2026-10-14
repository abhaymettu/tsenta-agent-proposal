"""Host canary scanner for openclaw/canary.sh (551 v10, v11; operator 19:48). Run with `python3 -I`.

The canary arrives as the first line of stdin, never in argv, and is never printed. Each root is resolved to its
realpath and scanned in one of two modes: `--full ROOT` (every regular file) or `--recent ROOT` (only regular files
whose ctime is at or after the stamp file's mtime; the canary is created after the stamp, and ctime cannot be set back).

Every directory is opened with O_DIRECTORY|O_NOFOLLOW and checked by fstat against the device and inode seen when it was
listed. Every entry is then lstat'ed and opened relative to that directory fd, so a renamed or swapped path cannot
redirect the walk. Every entry NAME is searched for the canary: a name hit is a HIT, and its path is only ever printed
redacted. Only regular files are read. Symlinks, FIFOs, sockets and devices are counted and never opened. A regular
file is opened O_RDONLY|O_NONBLOCK|O_NOFOLLOW|O_CLOEXEC, and fstat must show the same regular file (type, device,
inode) with the ctime filter re-applied. It is read in 1 MiB chunks that overlap by len(canary)-1. The walk does not
cross filesystems.
UNVERIFIED (never counted as clean): denied, oversize (256 MiB cap), changed (type or identity differs between the
lstat and the fstat, for a file or a directory), or timeout (the root hit its time limit).
VANISHED (551 v17 R2, operator 20:19): an entry that scandir listed, but that was gone (ENOENT) at its lstat, open or
dir-open. It is counted and its path printed, but it is not UNVERIFIED, because it no longer exists. A root that does not
exist stays denied. Content deleted before the scan reached it is out of scope.

Output, one tab-separated line per root:
  realpath  mode  hits  name_hits  files_read  bytes_read  skipped_old  symlink  fifo  socket  device  denied  oversize
  changed  timeout  vanished  sample
`sample` is up to 3 unverified paths, then up to 3 hit paths, then up to 3 vanished paths, joined by '|'. These are paths only, never contents,
and any canary occurrence in a path is replaced by <REDACTED-CANARY>.
Exit: 1 if any hit (content or name); 2 if none, but something is UNVERIFIED; 0 if every root is clean and fully examined.
`--control` checks the matcher itself: it searches the canary's own bytes, held in memory, with tiny chunks so the
hit crosses a boundary, and prints "control hits N". The walker is covered by tests/test_scan_host.py.
"""
import argparse, errno, os, stat, sys, time

FIELDS = ('hits', 'name_hits', 'files_read', 'bytes_read', 'skipped_old', 'symlink', 'fifo', 'socket', 'device',
          'denied', 'oversize', 'changed', 'timeout', 'vanished')
REDACT = b'<REDACTED-CANARY>'


def contains(chunks, needle):
    """True if needle occurs in the concatenation of chunks, keeping only len(needle)-1 bytes between chunks."""
    tail = b''
    for c in chunks:
        if needle in tail + c:
            return True
        tail = (tail + c)[-(len(needle) - 1):] if len(needle) > 1 else b''
    return False


def scan_root(root, needle, recent_after, chunk, max_bytes, timeout):
    r = dict.fromkeys(FIELDS, 0)
    unverified, hit_paths, gone = [], [], []
    deadline = time.monotonic() + timeout
    code = lambda e: errno.errorcode.get(e.errno, str(e.errno))

    def unv(kind, path, why):
        r[kind] += 1
        unverified.append(f'{path} ({why})')

    def lost(e, path, kind='denied'):  # ENOENT after scandir listed the entry: vanished, not UNVERIFIED (551 v17 R2)
        if e.errno == errno.ENOENT:
            r['vanished'] += 1
            gone.append(f'{path} (vanished)')
        else:
            unv(kind, path, code(e))

    try:
        rst = os.stat(root)  # the root itself is already a realpath
    except OSError as e:
        unv('denied', root, f'root: {code(e)}')
        return r, unverified, hit_paths, gone
    if not stat.S_ISDIR(rst.st_mode):
        unv('changed', root, 'root is not a directory')
        return r, unverified, hit_paths, gone
    root_dev = rst.st_dev
    stack = [(root, rst.st_dev, rst.st_ino)]
    while stack:
        if time.monotonic() > deadline:
            r['timeout'] = 1
            unverified.append(f'{root} (time limit {timeout:g}s; walk stopped with {len(stack)} dirs left)')
            break
        d, dev, ino = stack.pop()
        try:
            dfd = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError as e:
            if e.errno in (errno.ELOOP, errno.ENOTDIR):
                unv('changed', d, code(e))
            elif d == root:
                unv('denied', d, code(e))  # a missing root stays denied
            else:
                lost(e, d)
            continue
        try:
            dst = os.fstat(dfd)
            if (dst.st_dev, dst.st_ino) != (dev, ino):
                unv('changed', d, 'directory identity changed since listed')
                continue
            try:
                names = [e.name for e in os.scandir(dfd)]
            except OSError as e:
                unv('denied', d, code(e))
                continue
            for name in names:
                p = os.path.join(d, name)
                if needle in os.fsencode(name):
                    r['name_hits'] += 1
                    hit_paths.append(p + ' (name)')
                try:
                    st = os.lstat(name, dir_fd=dfd)
                except OSError as e:
                    lost(e, p)
                    continue
                m = st.st_mode
                if stat.S_ISDIR(m):
                    if st.st_dev == root_dev:
                        stack.append((p, st.st_dev, st.st_ino))
                    continue
                if stat.S_ISLNK(m):
                    r['symlink'] += 1; continue
                if stat.S_ISFIFO(m):
                    r['fifo'] += 1; continue
                if stat.S_ISSOCK(m):
                    r['socket'] += 1; continue
                if not stat.S_ISREG(m):
                    r['device'] += 1; continue
                if recent_after is not None and st.st_ctime < recent_after:
                    r['skipped_old'] += 1; continue
                if st.st_size > max_bytes:
                    unv('oversize', p, f'oversize {st.st_size} > {max_bytes}'); continue
                try:
                    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
                except OSError as e:
                    lost(e, p, 'changed' if e.errno == errno.ELOOP else 'denied'); continue
                try:
                    fst = os.fstat(fd)
                    if not stat.S_ISREG(fst.st_mode) or (fst.st_dev, fst.st_ino) != (st.st_dev, st.st_ino):
                        unv('changed', p, 'type or identity changed between lstat and open'); continue
                    if recent_after is not None and fst.st_ctime < recent_after:
                        r['skipped_old'] += 1; continue
                    if fst.st_size > max_bytes:
                        unv('oversize', p, f'oversize {fst.st_size} > {max_bytes}'); continue
                    n, tail, found = 0, b'', False
                    while True:
                        if time.monotonic() > deadline:
                            raise TimeoutError
                        b = os.read(fd, chunk)
                        if not b:
                            break
                        n += len(b)
                        if n > max_bytes:
                            raise OverflowError
                        if needle in tail + b:
                            found = True
                        tail = (tail + b)[-(len(needle) - 1):]
                except TimeoutError:
                    r['timeout'] = 1
                    unverified.append(f'{p} (time limit {timeout:g}s while reading)')
                    stack.clear()
                    break
                except OverflowError:
                    unv('oversize', p, f'grew past {max_bytes} while reading'); continue
                except OSError as e:
                    unv('denied', p, f'{code(e)} while reading'); continue
                finally:
                    os.close(fd)
                r['files_read'] += 1
                r['bytes_read'] += n
                if found:
                    r['hits'] += 1
                    hit_paths.append(p)
        finally:
            os.close(dfd)
    return r, unverified, hit_paths, gone


def redact(text, needle):
    return os.fsdecode(os.fsencode(text).replace(needle, REDACT))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--stamp', help='file whose mtime bounds --recent roots')
    ap.add_argument('--full', action='append', default=[])
    ap.add_argument('--recent', action='append', default=[])
    ap.add_argument('--chunk', type=int, default=1 << 20)
    ap.add_argument('--max-bytes', type=int, default=256 << 20)
    ap.add_argument('--root-timeout', type=float, default=60.0)
    ap.add_argument('--control', action='store_true')
    a = ap.parse_args()
    needle = sys.stdin.buffer.readline().rstrip(b'\r\n')
    if len(needle) < 16:
        sys.exit('scan-host: no canary on stdin')
    if a.control:
        print('control hits', int(contains((needle[i:i + 3] for i in range(0, len(needle), 3)), needle)))
        return 0
    if a.recent and not a.stamp:
        sys.exit('scan-host: --recent needs --stamp')
    after = os.stat(a.stamp).st_mtime if a.stamp else None
    worst = 0
    for mode, roots in (('full', a.full), ('recent', a.recent)):
        for root in roots:
            real = os.path.realpath(root)
            r, unv, hits, gone = scan_root(real, needle, after if mode == 'recent' else None, a.chunk, a.max_bytes, a.root_timeout)
            sample = redact('|'.join(unv[:3] + hits[:3] + gone[:3]), needle).replace('\t', ' ').replace('\n', ' ')
            print('\t'.join([redact(real, needle), mode] + [str(r[f]) for f in FIELDS] + [sample]), flush=True)
            bad = r['denied'] or r['oversize'] or r['changed'] or r['timeout']
            worst = max(worst, 3 if (r['hits'] or r['name_hits']) else (2 if bad else 0))
    needle = None
    return {3: 1, 2: 2, 0: 0}[worst]


if __name__ == '__main__':
    sys.exit(main())
