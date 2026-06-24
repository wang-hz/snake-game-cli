import curses
from collections import deque

import pytest

import snake_game_cli
from snake_game_cli import (
    TICK_ACCEL,
    TICK_BASE,
    TICK_MIN,
    Direction,
    Game,
    _load_high_score,
    _normalize_key,
    _save_high_score,
    _tick_interval,
)


def make_game() -> Game:
    """A 10x10 logical map (screen 10x20 with 1x2 scaling). Snake starts at (5, 5)."""
    return Game(10, 20)


# --- _normalize_key ---------------------------------------------------------


@pytest.mark.parametrize(
    'ch, expected',
    [
        (ord('A'), ord('a')),
        (ord('Z'), ord('z')),
        (ord('W'), ord('w')),
        (ord('a'), ord('a')),  # lowercase unchanged
        (ord('z'), ord('z')),
        (ord('5'), ord('5')),  # non-letter unchanged
        (curses.KEY_UP, curses.KEY_UP),  # special keys (> 'Z') unchanged
    ],
)
def test_normalize_key(ch, expected):
    assert _normalize_key(ch) == expected


# --- _tick_interval ---------------------------------------------------------


def test_tick_interval_base_at_zero():
    assert _tick_interval(0) == TICK_BASE


def test_tick_interval_decreases_with_score():
    assert _tick_interval(5) == pytest.approx(TICK_BASE - 5 * TICK_ACCEL)
    assert _tick_interval(5) < _tick_interval(0)


def test_tick_interval_floored_at_min():
    assert _tick_interval(10_000) == TICK_MIN


# --- Game construction ------------------------------------------------------


def test_initial_state():
    game = make_game()
    assert game.map_height == 10
    assert game.map_width == 10
    assert game.snake_body[0] == (5, 5)
    assert game.snake_length == 5
    assert game.direction == Direction.UP
    assert game.next_direction is None
    assert game.score == 0
    assert not game.game_over
    assert not game.game_won
    # Food is placed on an available (non-border, non-snake) cell.
    assert game.food is not None
    assert not game.is_border(*game.food)
    assert game.food not in game.snake_body_set


# --- is_border --------------------------------------------------------------


@pytest.mark.parametrize('pos', [(0, 5), (9, 5), (5, 0), (5, 9), (0, 0)])
def test_is_border_true(pos):
    assert make_game().is_border(*pos)


@pytest.mark.parametrize('pos', [(1, 1), (5, 5), (8, 8)])
def test_is_border_false(pos):
    assert not make_game().is_border(*pos)


# --- _to_screen_cells (1x2 scaling) -----------------------------------------


def test_to_screen_cells():
    game = make_game()
    assert game._to_screen_cells(3, 4) == [(3, 8), (3, 9)]


# --- handle_input -----------------------------------------------------------


def test_handle_input_sets_next_direction():
    game = make_game()  # direction UP
    assert game.handle_input(curses.KEY_LEFT) is True
    assert game.next_direction == Direction.LEFT


def test_handle_input_accepts_uppercase_wasd():
    game = make_game()
    assert game.handle_input(ord('A')) is True
    assert game.next_direction == Direction.LEFT


def test_handle_input_rejects_reverse():
    game = make_game()  # direction UP
    assert game.handle_input(ord('s')) is False  # DOWN is opposite of UP
    assert game.next_direction is None


def test_handle_input_ignores_unrelated_key():
    game = make_game()
    assert game.handle_input(ord('x')) is False
    assert game.next_direction is None


# --- update -----------------------------------------------------------------


def test_update_applies_buffered_direction():
    game = make_game()
    game.handle_input(curses.KEY_LEFT)
    game.update()
    assert game.direction == Direction.LEFT
    assert game.next_direction is None
    assert game.snake_body[0] == (5, 4)


def test_update_grows_until_full_length():
    game = make_game()  # length 5, body of 1
    game.food = None  # avoid accidental eating during the walk
    game._available.clear()
    game.direction = Direction.LEFT
    for _ in range(3):
        game.update()
    # 1 initial + 3 moves, length 5 not yet reached, so no tail removed.
    assert len(game.snake_body) == 4
    assert not game.game_over


def test_update_wall_collision_ends_game():
    game = make_game()
    game.snake_body = deque([(1, 5)])
    game.snake_body_set = {(1, 5)}
    game.snake_length = 1
    game.direction = Direction.UP  # next head (0, 5) is the border
    game.update()
    assert game.game_over
    assert game.score == 0


def test_update_self_collision_ends_game():
    game = make_game()
    game.snake_body = deque([(5, 5), (4, 5)])
    game.snake_body_set = {(5, 5), (4, 5)}
    game.snake_length = 2
    game.direction = Direction.UP  # next head (4, 5) is on the body
    game.update()
    assert game.game_over


def test_update_eats_food():
    game = make_game()
    game.food = (4, 5)  # directly above the head; direction is UP
    game.update()
    assert game.score == 1
    assert game.snake_length == 6
    assert (4, 5) in game.snake_body_set
    assert game.food != (4, 5)  # a new food was picked
    assert not game.game_over


def test_update_win_when_board_filled():
    game = make_game()
    game.food = (4, 5)
    game._available = set()  # nothing left to place new food after eating
    game.update()
    assert game.game_won
    assert game.game_over
    assert game.score == 1


def test_update_noop_after_game_over():
    game = make_game()
    game.game_over = True
    before = list(game.snake_body)
    game.update()
    assert list(game.snake_body) == before


# --- high score persistence -------------------------------------------------


@pytest.fixture
def high_score_file(tmp_path, monkeypatch):
    path = tmp_path / 'snake-game-cli' / 'highscore'
    monkeypatch.setattr(snake_game_cli, '_high_score_path', lambda: path)
    return path


def test_save_then_load_roundtrip(high_score_file):
    _save_high_score(42)
    assert _load_high_score() == 42


def test_save_creates_parent_dir(high_score_file):
    assert not high_score_file.parent.exists()
    _save_high_score(7)
    assert high_score_file.exists()


def test_load_missing_returns_zero(high_score_file):
    assert _load_high_score() == 0


def test_load_invalid_returns_zero(high_score_file):
    high_score_file.parent.mkdir(parents=True)
    high_score_file.write_text('not a number')
    assert _load_high_score() == 0


def test_load_negative_clamped_to_zero(high_score_file):
    high_score_file.parent.mkdir(parents=True)
    high_score_file.write_text('-5')
    assert _load_high_score() == 0


# --- get_displays -----------------------------------------------------------


def test_get_displays_layers():
    game = make_game()
    border, body, food, head = game.get_displays()
    # Head is the single starting cell expanded to two screen cells.
    assert head == [(5, 10), (5, 11)]
    # Only the head exists initially, so body is empty.
    assert body == []
    # Food occupies two screen cells.
    assert len(food) == 2
    assert len(border) > 0
