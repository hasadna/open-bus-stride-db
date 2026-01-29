
def test(get_db):
    db = get_db()
    with db.get_session() as session:
        assert session.execute("SELECT 1").scalar() == 1
    assert "poolclass" not in db._create_engine_kwargs


def test_nullpool(get_db):
    db = get_db(poolclass_nullpool=True)
    with db.get_session() as session:
        assert session.execute("SELECT 1").scalar() == 1
    assert db._create_engine_kwargs["poolclass"].__name__ == "NullPool"
