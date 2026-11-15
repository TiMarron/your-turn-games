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


# ── Games are identified by game_type (the portal slug), not by directory ─────

from harness.authors import duplicate_slugs, pair_by_slug  # noqa: E402

OWNED = {"game_type": "infinite-xo", "authors": ["owner"]}


def test_hijack_via_game_type_in_new_dir_is_caught():
    base = {"games/infinite-xo": OWNED}
    head = {"games/infinite-xo": OWNED,
            "games/new": {"game_type": "infinite-xo", "authors": ["attacker"]}}
    pairs = pair_by_slug(base, head, {"games/new"})
    assert pairs == {"infinite-xo": (OWNED, head["games/new"])}
    errs, _ = check_pr(pairs, "attacker")
    assert errs and "maintainer" in errs[0]
    assert duplicate_slugs(head) == ["infinite-xo"]


def test_moved_dir_is_the_same_game():
    meta = {"game_type": "x", "authors": ["alice"]}
    pairs = pair_by_slug({"games/x": meta}, {"games/y": meta}, {"games/x", "games/y"})
    assert pairs == {"x": (meta, meta)}
    assert check_pr(pairs, "mallory")[0]
    assert check_pr(pairs, "alice")[0] == []


def test_slug_change_is_new_game_plus_removal():
    old = {"game_type": "x", "authors": ["alice"]}
    new = {"game_type": "z", "authors": ["alice"]}
    pairs = pair_by_slug({"games/x": old}, {"games/x": new}, {"games/x"})
    assert pairs == {"z": (None, new), "x": (old, None)}


def test_slug_defaults_to_dir_name():
    meta = {"authors": ["alice"]}
    pairs = pair_by_slug({}, {"games/foo": meta}, {"games/foo"})
    assert pairs == {"foo": (None, meta)}
