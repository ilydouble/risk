import zipfile

import pytest
from service.adapters.archive import unpack


@pytest.mark.parametrize(
    "members",
    [
        [("../outside", b"bad")],
        [("/absolute", b"bad")],
        [("folder\\outside", b"bad")],
        [("duplicate", b"first"), ("duplicate", b"second")],
        [(str(i), b"x") for i in range(129)],
    ],
)
def test_untrusted_zip_paths_duplicates_and_count(tmp_path, members):
    archive = tmp_path / "input.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        for name, contents in members:
            stream.writestr(name, contents)
    with pytest.raises(ValueError):
        unpack(archive, tmp_path / "output")
    assert not (tmp_path / "outside").exists()
