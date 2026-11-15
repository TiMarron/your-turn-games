from harness.authors import check_pr, metadata_problems


def test_new_game_author_must_be_listed():
    errs, _ = check_pr({"games/x": (None, {"authors": ["alice"]})}, "Alice")
    assert errs == []
    errs, _ = check_pr({"games/x": (None, {"authors": ["alice"]})}, "bob")
    assert errs


def test_change_needs_base_author():
    base, head = {"authors": ["alice"]}, {"authors": ["alice", "bob"]}
    assert check_pr({"games/x": (base, head)}, "alice")[0] == []
    errs, _ = check_pr({"games/x": (base, {"authors": ["bob"]})}, "bob")
    assert errs and "maintainer" in errs[0]


def test_authors_change_notice():
    _, notes = check_pr(
        {"games/x": ({"authors": ["alice"]}, {"authors": ["alice", "bob"]})}, "alice"
    )
    assert notes == ["games/x: authors changed: +bob"]


def test_authors_removed_notice():
    _, notes = check_pr(
        {"games/x": ({"authors": ["alice", "bob"]}, {"authors": ["alice"]})}, "alice"
    )
    assert notes == ["games/x: authors changed: -bob"]


def test_deleted_game_needs_base_author():
    assert check_pr({"games/x": ({"authors": ["alice"]}, None)}, "mallory")[0]
    assert check_pr({"games/x": ({"authors": ["alice"]}, None)}, "alice")[0] == []


def test_invalid_head_metadata_reported():
    errs, _ = check_pr({"games/x": (None, {"authors": []})}, "alice")
    assert errs


def test_base_without_authors_needs_maintainer():
    """A game that predates `authors`: nobody is an author on the base branch."""
    errs, _ = check_pr({"games/x": ({}, {"authors": ["alice"]})}, "alice")
    assert errs and "maintainer" in errs[0]


def test_metadata_problems():
    assert metadata_problems({"authors": ["ok-name"]}) == []
    for bad in ({}, {"authors": []}, {"authors": "alice"}, {"authors": ["-bad"]},
                {"authors": [1]}, {"authors": ["a" * 40]}):
        assert metadata_problems(bad), bad


def test_maintainer_may_change_any_game():
    errs, notes = check_pr({"games/x": ({}, {"authors": ["alice"]})}, "Owner",
                           maintainers=["owner"])
    assert errs == [] and notes == ["games/x: authors changed: +alice"]
    errs, _ = check_pr({"games/x": ({}, {"authors": []})}, "owner", maintainers=["owner"])
    assert errs  # metadata problems still reported
