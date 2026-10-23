"""Fail-closed contract for R2 read-back verified storage, no real cloud calls."""
import hashlib
import io

import pytest

from shorts_studio.r2_verified_transfer import (
    IntegrityError, plan_upload, upload_verified,
)


class RemoteError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class MemoryR2:
    def __init__(self, *, permit=True, corrupt_reads=False):
        self.objects = {}
        self.permit = permit
        self.corrupt_reads = corrupt_reads
        self.calls = []

    def head_bucket(self, **kwargs):
        self.calls.append("head_bucket")
        if not self.permit:
            raise RemoteError("AccessDenied")
        return {}

    def head_object(self, *, Bucket, Key):
        self.calls.append("head_object")
        if Key not in self.objects:
            raise RemoteError("404")
        return {"ContentLength": len(self.objects[Key])}

    def put_object(self, *, Bucket, Key, Body, ContentLength, Metadata,
                   IfNoneMatch, StorageClass):
        self.calls.append("put_object")
        assert StorageClass == "STANDARD"
        assert IfNoneMatch == "*"
        assert Metadata["sha256"] == Key.rsplit("/", 1)[-1].split(".")[0]
        if Key in self.objects:
            raise RemoteError("PreconditionFailed")
        content = Body.read()
        assert ContentLength == len(content)
        self.objects[Key] = content

    def get_object(self, *, Bucket, Key):
        self.calls.append("get_object")
        content = self.objects[Key]
        if self.corrupt_reads:
            content = b"damaged" + content
        return {"Body": io.BytesIO(content)}


def test_plan_is_local_only_and_content_addressed(tmp_path):
    source = tmp_path / "shard.mkv"
    source.write_bytes(b"safe-data" * 100)
    p = plan_upload(source, prefix="episode2/sha256", max_bytes=4096)
    assert p["size_bytes"] == 900
    assert p["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert p["key"] == "shorts-studio/episode2/sha256/" + p["sha256"] + ".mkv"
    assert p["status"] == "DRY_RUN"
    assert p["authorized_to_cleanup_local"] is False


def test_dry_run_never_touches_remote_even_if_s3_is_absent(tmp_path):
    source = tmp_path / "one.mp4"
    source.write_bytes(b"x" * 30)
    result = upload_verified(None, source, bucket="shorts-studio-media",
                             prefix="episode2", max_bytes=4096, apply=False)
    assert result["status"] == "DRY_RUN"
    assert result["authorized_to_cleanup_local"] is False


def test_apply_upload_readback_and_sha256(tmp_path):
    source = tmp_path / "sample.mkv"
    content = b"native-shard" * 150
    source.write_bytes(content)
    cloud = MemoryR2()
    result = upload_verified(cloud, source, bucket="shorts-studio-media",
                             prefix="episode2", max_bytes=4096, apply=True)
    assert result["status"] == "VERIFIED"
    assert result["verified_remote_sha256"] == hashlib.sha256(content).hexdigest()
    assert result["authorized_to_cleanup_local"] is False
    assert cloud.objects[result["key"]] == content
    assert cloud.calls == ["head_bucket", "head_object", "put_object", "get_object"]


def test_idempotent_reupload_verifies_existing_bytes(tmp_path):
    source = tmp_path / "sample.mkv"
    source.write_bytes(b"foo" * 80)
    cloud = MemoryR2()
    first = upload_verified(cloud, source, bucket="shorts-studio-media",
                            prefix="episode2", max_bytes=4096, apply=True)
    second = upload_verified(cloud, source, bucket="shorts-studio-media",
                             prefix="episode2", max_bytes=4096, apply=True)
    assert second["status"] == "VERIFIED_EXISTING"
    assert second["verified_remote_sha256"] == first["sha256"]
    assert cloud.calls.count("put_object") == 1


def test_existing_remote_collision_is_never_overwritten(tmp_path):
    source = tmp_path / "sample.mkv"
    source.write_bytes(b"foo" * 80)
    cloud = MemoryR2()
    key = plan_upload(source, prefix="episode2", max_bytes=4096)["key"]
    cloud.objects[key] = b"bad" * 80
    with pytest.raises(IntegrityError):
        upload_verified(cloud, source, bucket="shorts-studio-media",
                        prefix="episode2", max_bytes=4096, apply=True)
    assert cloud.objects[key] == b"bad" * 80
    assert cloud.calls.count("put_object") == 0


def test_corrupt_readback_never_claims_verified_or_deletes_local(tmp_path):
    source = tmp_path / "sample.mkv"
    source.write_bytes(b"real" * 20)
    cloud = MemoryR2(corrupt_reads=True)
    with pytest.raises(IntegrityError):
        upload_verified(cloud, source, bucket="shorts-studio-media",
                        prefix="episode2", max_bytes=4096, apply=True)
    assert source.read_bytes() == b"real" * 20


def test_reject_symlink_swap_before_put(tmp_path):
    """A file replaced after hashing must never be uploaded by following a link."""
    source = tmp_path / "sample.mkv"
    secret = tmp_path / "private.bin"
    source.write_bytes(b"original-data")
    secret.write_bytes(b"must-never-leave-the-host")

    class SwappingR2(MemoryR2):
        def head_bucket(self, **kwargs):
            super().head_bucket(**kwargs)
            source.unlink()
            source.symlink_to(secret)

    cloud = SwappingR2()
    with pytest.raises((IntegrityError, ValueError, OSError)):
        upload_verified(cloud, source, bucket="shorts-studio-media",
                        prefix="episode2", max_bytes=4096, apply=True)
    assert "put_object" not in cloud.calls
    assert cloud.objects == {}


def test_reject_changed_bytes_before_put(tmp_path):
    """Never PUT a source that changed after local content-addressing."""
    source = tmp_path / "sample.mkv"
    source.write_bytes(b"original-data")

    class MutatingR2(MemoryR2):
        def head_bucket(self, **kwargs):
            super().head_bucket(**kwargs)
            source.write_bytes(b"different-bytes")

    cloud = MutatingR2()
    with pytest.raises(IntegrityError):
        upload_verified(cloud, source, bucket="shorts-studio-media",
                        prefix="episode2", max_bytes=4096, apply=True)
    assert "put_object" not in cloud.calls
    assert cloud.objects == {}


def test_permission_error_does_not_trigger_new_bucket_or_upload(tmp_path):
    source = tmp_path / "sample.mkv"
    source.write_bytes(b"hi")
    cloud = MemoryR2(permit=False)
    with pytest.raises(RemoteError):
        upload_verified(cloud, source, bucket="shorts-studio-media",
                        prefix="episode2", max_bytes=4096, apply=True)
    assert cloud.calls == ["head_bucket"]


@pytest.mark.parametrize("bad_prefix", ["", "../evil", "foo//bar", "/tmp", "s p a c e", "Upper"])
def test_reject_unsafe_remote_key_prefix(tmp_path, bad_prefix):
    source = tmp_path / "sample.mkv"
    source.write_bytes(b"x")
    with pytest.raises(ValueError):
        plan_upload(source, prefix=bad_prefix, max_bytes=4096)


def test_reject_oversize_and_unapproved_file_types(tmp_path):
    source = tmp_path / "sample.mkv"
    source.write_bytes(b"x" * 11)
    with pytest.raises(ValueError):
        plan_upload(source, prefix="episode2", max_bytes=10)
    source2 = tmp_path / "secret.env"
    source2.write_text("hello")
    with pytest.raises(ValueError):
        plan_upload(source2, prefix="episode2", max_bytes=4096)


def test_reject_symlink_even_if_target_is_file(tmp_path):
    source = tmp_path / "sample.mkv"
    source.write_bytes(b"x")
    link = tmp_path / "link.mkv"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        plan_upload(link, prefix="episode2", max_bytes=4096)


def test_invalid_bucket_is_rejected_before_network(tmp_path):
    source = tmp_path / "sample.mkv"
    source.write_bytes(b"x")
    cloud = MemoryR2()
    with pytest.raises(ValueError):
        upload_verified(cloud, source, bucket="invalid bucket",
                        prefix="episode2", max_bytes=4096, apply=True)
    assert cloud.calls == []
