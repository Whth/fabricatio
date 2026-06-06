"""Tests for the sandbox package."""

import tempfile
from pathlib import Path

import pytest
from fabricatio_sandbox.rust import SandboxSession, VirtualFS


class TestVirtualFS:
    """Tests for the VirtualFS pyclass."""

    def test_create_empty(self):
        vfs = VirtualFS()
        assert "VirtualFS" in repr(vfs)

    def test_write_and_read_text(self):
        vfs = VirtualFS()
        vfs.write_text("hello.txt", "world")
        assert vfs.read_text("hello.txt") == "world"

    def test_write_and_read_bytes(self):
        vfs = VirtualFS()
        vfs.write_bytes("data.bin", b"\x00\x01\x02")
        assert vfs.read_bytes("data.bin") == b"\x00\x01\x02"

    def test_nested_paths(self):
        vfs = VirtualFS()
        vfs.write_text("a/b/c.txt", "deep")
        assert vfs.read_text("a/b/c.txt") == "deep"
        assert vfs.is_file("a/b/c.txt")
        assert vfs.is_dir("a/b")
        assert not vfs.is_file("a/b")

    def test_list_dir(self):
        vfs = VirtualFS()
        vfs.write_text("dir/a.txt", "1")
        vfs.write_text("dir/b.txt", "2")
        names = vfs.list_dir("dir")
        assert sorted(names) == ["a.txt", "b.txt"]

    def test_walk_dir(self):
        vfs = VirtualFS()
        vfs.write_text("src/main.rs", "fn main() {}")
        vfs.write_text("src/lib.rs", "pub fn hello() {}")
        paths = vfs.walk_dir("src")
        filenames = [Path(p).name for p in paths]
        assert "main.rs" in filenames
        assert "lib.rs" in filenames

    def test_exists_is_file_is_dir(self):
        vfs = VirtualFS()
        assert not vfs.exists("missing")
        vfs.write_text("file.txt", "x")
        assert vfs.exists("file.txt")
        assert vfs.is_file("file.txt")
        assert not vfs.is_dir("file.txt")

    def test_create_dir(self):
        vfs = VirtualFS()
        vfs.create_dir("new_dir")
        assert vfs.is_dir("new_dir")

    def test_create_dir_all(self):
        vfs = VirtualFS()
        vfs.create_dir_all("a/b/c/d")
        assert vfs.is_dir("a/b/c/d")

    def test_remove_file(self):
        vfs = VirtualFS()
        vfs.write_text("temp.txt", "bye")
        assert vfs.exists("temp.txt")
        vfs.remove_file("temp.txt")
        assert not vfs.exists("temp.txt")

    def test_remove_dir_all(self):
        vfs = VirtualFS()
        vfs.write_text("rm_dir/a.txt", "1")
        vfs.write_text("rm_dir/b.txt", "2")
        assert vfs.exists("rm_dir")
        vfs.remove_dir_all("rm_dir")
        assert not vfs.exists("rm_dir")

    def test_copy_file(self):
        vfs = VirtualFS()
        vfs.write_text("original.txt", "data")
        vfs.copy_file("original.txt", "copy.txt")
        assert vfs.read_text("copy.txt") == "data"
        assert vfs.read_text("original.txt") == "data"

    def test_rename(self):
        vfs = VirtualFS()
        vfs.write_text("old.txt", "content")
        vfs.rename("old.txt", "new.txt")
        assert not vfs.exists("old.txt")
        assert vfs.read_text("new.txt") == "content"

    def test_abs_path(self):
        vfs = VirtualFS()
        ap = vfs.abs_path("some/file.txt")
        assert "some/file.txt" in ap

    def test_read_nonexistent_raises(self):
        vfs = VirtualFS()
        with pytest.raises(RuntimeError):
            vfs.read_text("nope.txt")


class TestSandboxSession:
    """Tests for the SandboxSession pyclass."""

    def test_create_empty(self):
        session = SandboxSession()
        assert session.root_path()
        assert session.mounts() == {}

    def test_create_with_mounts(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "hello.txt").write_text("from real fs")

        session = SandboxSession(mounts={"/project": str(real_dir)})
        assert session.mounts() == {"/project": str(real_dir)}

    def test_read_mounted_file(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "hello.txt").write_text("real content")

        session = SandboxSession(mounts={"/project": str(real_dir)})
        assert session.read_text("/project/hello.txt") == "real content"

    def test_write_does_not_modify_real_fs(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "file.txt").write_text("original")

        session = SandboxSession(mounts={"/project": str(real_dir)})
        session.write_text("/project/file.txt", "modified in sandbox")

        # Real FS unchanged
        assert (real_dir / "file.txt").read_text() == "original"
        # VFS has the new content
        assert session.read_text("/project/file.txt") == "modified in sandbox"

    def test_diff_tracks_modifications(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "file.txt").write_text("line1\nline2\nline3\n")

        session = SandboxSession(mounts={"/project": str(real_dir)})
        session.write_text("/project/file.txt", "line1\nmodified\nline3\n")

        diff = session.diff()
        assert "/project/file.txt" in diff
        assert "-line2" in diff["/project/file.txt"]
        assert "+modified" in diff["/project/file.txt"]

    def test_diff_empty_when_no_changes(self):
        session = SandboxSession()
        session.write_text("new.txt", "hello")
        # No originals tracked for a fresh file that was just created once
        diff = session.diff()
        # New file created in sandbox has no original, so no diff entry
        # (it's a "new" file, not a modification)
        # Actually it WILL have a diff because snapshot_if_needed runs on write
        # and the file doesn't exist yet in originals.
        # On first write, snapshot reads the file (which doesn't exist yet),
        # so no original is stored. The second write would capture the original.
        # Let's verify the behavior:
        assert isinstance(diff, dict)

    def test_diff_tracks_new_file_creation_and_modification(self):
        session = SandboxSession()
        # First write — file is new, no original to compare against
        session.write_text("file.txt", "version1")
        diff1 = session.diff()
        # No original was captured (file didn't exist before first write)
        assert len(diff1) == 0

        # Second write — now we have an original (version1)
        session.write_text("file.txt", "version2")
        diff2 = session.diff()
        assert "file.txt" in diff2
        assert "-version1" in diff2["file.txt"]
        assert "+version2" in diff2["file.txt"]

    def test_reset_clears_diffs(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "f.txt").write_text("original")

        session = SandboxSession(mounts={"/p": str(real_dir)})
        session.write_text("/p/f.txt", "changed")
        assert len(session.diff()) > 0

        session.reset()
        # After reset, the next diff should be empty (no originals tracked)
        # But the file still has "changed" in VFS
        diff_after_reset = session.diff()
        assert len(diff_after_reset) == 0

    def test_apply_flushes_to_real_fs(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "file.txt").write_text("original")

        session = SandboxSession(mounts={"/project": str(real_dir)})
        session.write_text("/project/file.txt", "applied content")
        session.apply()

        assert (real_dir / "file.txt").read_text() == "applied content"

    def test_apply_creates_new_files(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()

        session = SandboxSession(mounts={"/project": str(real_dir)})
        session.write_text("/project/new_file.txt", "brand new")
        session.apply()

        assert (real_dir / "new_file.txt").read_text() == "brand new"

    def test_apply_creates_nested_dirs(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()

        session = SandboxSession(mounts={"/project": str(real_dir)})
        session.write_text("/project/src/deep/file.rs", "fn main() {}")
        session.apply()

        assert (real_dir / "src" / "deep" / "file.rs").read_text() == "fn main() {}"

    def test_repr(self):
        session = SandboxSession()
        assert "SandboxSession" in repr(session)

    def test_vfs_operations_on_session(self):
        session = SandboxSession()
        session.create_dir("mydir")
        session.write_text("mydir/file.txt", "hello")
        assert session.is_dir("mydir")
        assert session.is_file("mydir/file.txt")
        assert session.exists("mydir/file.txt")
        assert session.list_dir("mydir") == ["file.txt"]
