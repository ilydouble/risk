import pytest

from training.demo import generate
from training.pipeline import train


@pytest.fixture(scope="session")
def trained(tmp_path_factory):
    path = tmp_path_factory.mktemp("model")
    d = generate(100)
    report = train(d, path, epochs=3, patience=2, hidden=8, pretrain_epochs=2)
    return path, d, report
