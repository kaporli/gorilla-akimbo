"""Backup and exact restore for everything an in-game run touches: save folders, settings files, the modlist.

Nothing here deletes. A file or folder that has to go is moved into the run's quarantine folder.
Every copy is verified by SHA-256 before it counts.
"""
import hashlib, json, os, shutil, time


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def tree(root):
    """{relative path with /: sha} of every file under root; {} if root is missing."""
    out = {}
    if not os.path.isdir(root):
        return out
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root).replace('\\', '/')] = sha(p)
    return out


def copy_tree(src, dst):
    """copytree that keeps file times and the folder's own time."""
    shutil.copytree(src, dst, copy_function=shutil.copy2)
    st = os.stat(src)
    os.utime(dst, (st.st_atime, st.st_mtime))


def aside(path, qdir):
    """Move path into qdir under a unique name; returns the new path."""
    os.makedirs(qdir, exist_ok=True)
    name = os.path.basename(path.rstrip('/\\'))
    dst = os.path.join(qdir, f'{name}.{time.strftime("%H%M%S")}')
    n = 0
    while os.path.exists(dst):
        n += 1
        dst = os.path.join(qdir, f'{name}.{time.strftime("%H%M%S")}.{n}')
    shutil.move(path, dst)
    return dst


class SaveGuard:
    """The save folder (Saved Games/.../Cyberpunk 2077).

    snapshot(): hashes every file; copies AutoSave-*, QuickSave-*, PointOfNoReturnSave-* folders and the top level
    files to backup/. Other folders (ManualSave-*) are hashed only: a run never writes them, a change is reported.
    restore(): every copied folder and file is brought back to its snapshot hash (the differing one is moved to
    quarantine/ first), folders the run created are moved to quarantine/created/, then the whole folder is
    compared with the snapshot.
    """
    COPY = ('AutoSave-', 'QuickSave-', 'PointOfNoReturnSave-')

    def __init__(self, saves, backup, quarantine):
        self.saves, self.backup, self.q = saves, backup, quarantine
        self.snap = None      # {entry name: {relative path: sha}}; a top level file has {'': sha}

    def _entries(self):
        return {n: os.path.join(self.saves, n) for n in sorted(os.listdir(self.saves))}

    @staticmethod
    def _hash_entry(p):
        return {'': sha(p)} if os.path.isfile(p) else tree(p)

    def _copied(self, n):
        return os.path.isfile(os.path.join(self.saves, n)) or n.startswith(self.COPY)

    def snapshot(self):
        if os.path.exists(self.backup) and os.listdir(self.backup):
            raise SystemExit(f'save backup folder is not empty: {self.backup}')
        os.makedirs(self.backup, exist_ok=True)
        self.snap = {n: self._hash_entry(p) for n, p in self._entries().items()}
        copied = 0
        for n, p in self._entries().items():
            if not self._copied(n):
                continue
            d = os.path.join(self.backup, n)
            if os.path.isdir(p): copy_tree(p, d)
            else: shutil.copy2(p, d)
            if self._hash_entry(d) != self.snap[n]:
                raise SystemExit(f'save backup of {n} does not match the original; nothing launched')
            copied += 1
        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(self.backup) for f in fs)
        return {'entries': len(self.snap), 'copied': copied, 'files': sum(len(v) for v in self.snap.values()), 'bytes': size}

    def restore(self):
        """Returns (ok, notes). ok only when the folder equals the snapshot afterwards."""
        notes = []
        for n, p in self._entries().items():
            if n not in self.snap:
                notes.append(f'created by the run, moved to {aside(p, os.path.join(self.q, "created"))}')
        for n, want in sorted(self.snap.items()):
            p = os.path.join(self.saves, n)
            if os.path.exists(p) and self._hash_entry(p) == want:
                continue
            if not self._copied(n):
                notes.append(f'{n}: changed and not backed up (hash-only entry)')
                continue
            if os.path.exists(p):
                aside(p, os.path.join(self.q, 'changed'))
                notes.append(f'{n}: differed from the snapshot, moved aside, restored')
            else:
                notes.append(f'{n}: missing, restored')
            b = os.path.join(self.backup, n)
            if os.path.isdir(b): copy_tree(b, p)
            else: shutil.copy2(b, p)
        bad = []
        now = self._entries()
        if set(now) != set(self.snap):
            bad.append(f'entries differ: {sorted(set(now) ^ set(self.snap))}')
        for n, want in self.snap.items():
            if n in now and self._hash_entry(now[n]) != want:
                bad.append(f'{n} hash differs')
        return (not bad), notes + bad


class FileGuard:
    """Single files: copy before, put back after. A file that did not exist is moved aside if the run made it."""

    def __init__(self, backup, quarantine):
        self.backup, self.q = backup, quarantine
        self.items = []       # (path, sha or None, backup copy or None)

    def add(self, path):
        if os.path.isfile(path):
            os.makedirs(self.backup, exist_ok=True)
            b = os.path.join(self.backup, f'{len(self.items):02d}_{os.path.basename(path)}')
            shutil.copy2(path, b)
            if sha(b) != sha(path):
                raise SystemExit(f'backup of {path} does not match')
            self.items.append((path, sha(path), b))
        else:
            self.items.append((path, None, None))

    def restore(self):
        notes, bad = [], []
        for path, h, b in self.items:
            if h is None:
                if os.path.exists(path):
                    aside(path, os.path.join(self.q, 'files'))
                    notes.append(f'{path}: made by the run, moved aside')
                continue
            if not os.path.isfile(path) or sha(path) != h:
                if os.path.exists(path):
                    aside(path, os.path.join(self.q, 'files'))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                shutil.copy2(b, path)
                notes.append(f'{path}: restored')
            if sha(path) != h:
                bad.append(f'{path} hash differs after restore')
        return (not bad), notes + bad


def set_mod(data, name, on):
    """Flip one mod in modlist.txt bytes (CRLF kept). A missing mod is added at the top (highest priority) when on."""
    key = name.encode('utf8')
    lines = data.split(b'\r\n')
    for i, l in enumerate(lines):
        if l[1:] == key and l[:1] in (b'+', b'-'):
            lines[i] = (b'+' if on else b'-') + key
            return b'\r\n'.join(lines)
    if not on:
        return data
    lines.insert(1, b'+' + key)
    return b'\r\n'.join(lines)


def mod_state(data, name):
    key = name.encode('utf8')
    for l in data.split(b'\r\n'):
        if l[1:] == key and l[:1] in (b'+', b'-'):
            return l[:1] == b'+'
    return None


def edit_settings(path, changes):
    """changes {(group, name): value} in a game UserSettings.json; returns the old values."""
    with open(path, encoding='utf8') as f:
        d = json.load(f)
    old, want = {}, dict(changes)
    for g in d['data']:
        for o in g['options']:
            k = (g['group_name'], o['name'])
            if k in want:
                old[k] = o['value']
                o['value'] = want.pop(k)
    if want:
        raise SystemExit(f'settings not found in {path}: {sorted(want)}')
    with open(path, 'w', encoding='utf8', newline='\n') as f:
        json.dump(d, f, indent=4, ensure_ascii=False)
    return old
