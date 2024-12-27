@pytest.fixture(scope="function")
def pos(pos_session) -> Pos:  # type: ignore
    yield Pos()