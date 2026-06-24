import argparse
import curses
import os
import random
import sys
import time
from collections import deque
from curses import wrapper
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

TICK_BASE = 0.2
TICK_MIN = 0.08
TICK_ACCEL = 0.005
PAUSE_POLL_MS = 100
MIN_LINES = 16
MIN_COLS = 30

_Pos = tuple[int, int]


@dataclass(frozen=True)
class Difficulty:
    """A speed preset: starting tick, floor tick, and per-point acceleration."""

    label: str
    tick_base: float
    tick_min: float
    tick_accel: float


# Ordered slowest -> fastest. 'Normal' mirrors the historical TICK_* constants.
DIFFICULTIES: list[Difficulty] = [
    Difficulty('Easy', 0.28, 0.12, 0.004),
    Difficulty('Normal', TICK_BASE, TICK_MIN, TICK_ACCEL),
    Difficulty('Hard', 0.12, 0.05, 0.006),
]
DIFFICULTY_NAMES: list[str] = [d.label.lower() for d in DIFFICULTIES]
DEFAULT_DIFFICULTY_INDEX = DIFFICULTY_NAMES.index('normal')


def _normalize_key(ch: int) -> int:
    """Fold ASCII uppercase letters to lowercase so all key checks use one case."""
    if ord('A') <= ch <= ord('Z'):
        return ch + 32
    return ch


class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()


_DIRECTION_DELTA: dict[Direction, _Pos] = {
    Direction.UP: (-1, 0),
    Direction.DOWN: (1, 0),
    Direction.LEFT: (0, -1),
    Direction.RIGHT: (0, 1),
}


class Game:
    def __init__(self, screen_height: int, screen_width: int) -> None:
        self.game_over = False
        self.height_scale = 1
        self.width_scale = 2
        self.map_height = screen_height // self.height_scale
        self.map_width = screen_width // self.width_scale
        self.screen_height = self.map_height * self.height_scale
        self.screen_width = self.map_width * self.width_scale
        start: _Pos = (self.map_height // 2, self.map_width // 2)
        self.snake_body: deque[_Pos] = deque([start])
        self.snake_body_set: set[_Pos] = {start}
        self.snake_length = 5
        self.direction = Direction.UP
        self.next_direction: Direction | None = None
        self.score = 0
        self.game_won = False
        self._available: set[_Pos] = {
            (y, x) for y in range(1, self.map_height - 1) for x in range(1, self.map_width - 1)
        } - self.snake_body_set
        self.food: _Pos | None = self._pick_food()
        self._border_display = self._compute_border()

    def _compute_border(self) -> list[_Pos]:
        border = []
        for y in range(self.screen_height):
            for x in range(self.screen_width):
                if self.is_border(y // self.height_scale, x // self.width_scale):
                    border.append((y, x))
        return border

    def _to_screen_cells(self, gy: int, gx: int) -> list[_Pos]:
        return [
            (gy * self.height_scale + dy, gx * self.width_scale + dx)
            for dy in range(self.height_scale)
            for dx in range(self.width_scale)
        ]

    def handle_input(self, ch: int) -> bool:
        ch = _normalize_key(ch)
        if ch in (curses.KEY_UP, ord('w')) and self.direction != Direction.DOWN:
            self.next_direction = Direction.UP
            return True
        if ch in (curses.KEY_DOWN, ord('s')) and self.direction != Direction.UP:
            self.next_direction = Direction.DOWN
            return True
        if ch in (curses.KEY_LEFT, ord('a')) and self.direction != Direction.RIGHT:
            self.next_direction = Direction.LEFT
            return True
        if ch in (curses.KEY_RIGHT, ord('d')) and self.direction != Direction.LEFT:
            self.next_direction = Direction.RIGHT
            return True
        return False

    def update(self) -> None:
        if self.game_over:
            return
        if self.next_direction is not None:
            self.direction = self.next_direction
            self.next_direction = None
        y, x = self.get_next_snake_head()
        if self.is_border(y, x) or (y, x) in self.snake_body_set:
            self.game_over = True
            return
        ate = (y, x) == self.food
        self.snake_body.appendleft((y, x))
        self.snake_body_set.add((y, x))
        self._available.discard((y, x))
        if ate:
            self.snake_length += 1
            self.score += 1
            # Pick after discarding the new head so food never spawns under it.
            self.food = self._pick_food()
            if self.food is None:
                self.game_won = True
                self.game_over = True
        if self.snake_length < len(self.snake_body):
            removed = self.snake_body.pop()
            self.snake_body_set.discard(removed)
            self._available.add(removed)

    def get_next_snake_head(self) -> _Pos:
        y, x = self.snake_body[0]
        dy, dx = _DIRECTION_DELTA[self.direction]
        return y + dy, x + dx

    def is_border(self, y: int, x: int) -> bool:
        return y in (0, self.map_height - 1) or x in (0, self.map_width - 1)

    def _pick_food(self) -> _Pos | None:
        return random.choice(tuple(self._available)) if self._available else None

    def get_displays(self) -> list[list[_Pos]]:
        head = self._to_screen_cells(*self.snake_body[0])
        body = [
            cell for gy, gx in list(self.snake_body)[1:] for cell in self._to_screen_cells(gy, gx)
        ]
        food = self._to_screen_cells(*self.food) if self.food else []
        return [self._border_display, body, food, head]


def _high_score_path() -> Path:
    """Cross-platform location for the persisted high score (no extra deps)."""
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA')
        root = Path(base) if base else Path.home()
    else:
        base = os.environ.get('XDG_STATE_HOME')
        root = Path(base) if base else Path.home() / '.local' / 'state'
    return root / 'snake-game-cli' / 'highscore'


def _load_high_score() -> int:
    """Read the saved high score, returning 0 if missing or unreadable."""
    try:
        return max(0, int(_high_score_path().read_text().strip()))
    except (OSError, ValueError):
        return 0


def _save_high_score(score: int) -> None:
    """Persist the high score, silently ignoring any filesystem error."""
    path = _high_score_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(score))
    except OSError:
        pass


def _draw_too_small(stdscr: curses.window) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    msg = f'Terminal too small ({w}x{h}). Resize to at least {MIN_COLS}x{MIN_LINES}.'
    if h >= 1 and w >= len(msg):
        stdscr.addstr(h // 2, (w - len(msg)) // 2, msg)
    stdscr.refresh()


def _safe_addstr(stdscr: curses.window, y: int, x: int, text: str) -> None:
    """addstr that ignores the curses.error raised when writing at or past the
    screen edge (e.g. the bottom-right cell), so an oversized box never crashes."""
    try:
        stdscr.addstr(y, x, text)
    except curses.error:
        pass


def draw_centered_box(stdscr: curses.window, lines: list[str]) -> None:
    width = max(len(line) for line in lines) + 6
    height = len(lines) + 4
    screen_h, screen_w = stdscr.getmaxyx()
    if width > screen_w or height > screen_h:
        # The box can't fit the terminal: drop the border and just center the
        # text, clamped on-screen, so the key message stays readable instead of
        # rendering a broken half-box.
        y0 = max(0, (screen_h - len(lines)) // 2)
        for i, line in enumerate(lines):
            x = max(0, (screen_w - len(line)) // 2)
            _safe_addstr(stdscr, y0 + i, x, line)
        return
    y0 = (screen_h - height) // 2
    x0 = (screen_w - width) // 2
    _safe_addstr(stdscr, y0, x0, '┌' + '─' * (width - 2) + '┐')
    for i in range(1, height - 1):
        _safe_addstr(stdscr, y0 + i, x0, '│' + ' ' * (width - 2) + '│')
    _safe_addstr(stdscr, y0 + height - 1, x0, '└' + '─' * (width - 2) + '┘')
    for i, line in enumerate(lines):
        x = x0 + (width - len(line)) // 2
        _safe_addstr(stdscr, y0 + 2 + i, x, line)


def _start_screen_lines(high_score: int, difficulty_index: int) -> list[str]:
    lines = ['SNAKE  GAME', '']
    if high_score > 0:
        lines += [f'High Score: {high_score}', '']
    label = DIFFICULTIES[difficulty_index].label
    lines += [
        f'Difficulty:  ◄ {label} ►',
        '',
        '↑ / W    Move Up',
        '↓ / S    Move Down',
        '← / A    Move Left',
        '→ / D    Move Right',
        'P        Pause / Resume',
        'Q        Quit',
        '',
        '← / →    Change difficulty',
        'Enter    Start game',
    ]
    return lines


def draw_start_screen(stdscr: curses.window, high_score: int, difficulty_index: int) -> int | None:
    """Interactive start screen. Returns the chosen difficulty index, or None to quit."""
    stdscr.timeout(-1)
    while True:
        stdscr.erase()
        draw_centered_box(stdscr, _start_screen_lines(high_score, difficulty_index))
        stdscr.refresh()
        ch = _normalize_key(stdscr.getch())
        if ch == ord('q'):
            return None
        if ch in (curses.KEY_LEFT, ord('a')):
            difficulty_index = (difficulty_index - 1) % len(DIFFICULTIES)
        elif ch in (curses.KEY_RIGHT, ord('d')):
            difficulty_index = (difficulty_index + 1) % len(DIFFICULTIES)
        elif ch in (curses.KEY_ENTER, ord('\n'), ord('\r'), ord(' ')):
            return difficulty_index
        elif ch == curses.KEY_RESIZE and not _wait_for_resize(stdscr):
            return None


def _score_lines(game: Game, high_score: int, new_high: bool) -> list[str]:
    if new_high:
        return [f'Score: {game.score}', 'New High Score!']
    return [f'Score: {game.score}', f'High Score: {high_score}']


def draw_win_screen(stdscr: curses.window, game: Game, high_score: int, new_high: bool) -> None:
    lines = [
        'YOU  WIN!',
        *_score_lines(game, high_score, new_high),
        '',
        '[R] Play Again',
        '[Q] Quit',
    ]
    draw_centered_box(stdscr, lines)


def draw_game_over(stdscr: curses.window, game: Game, high_score: int, new_high: bool) -> None:
    lines = [
        'GAME  OVER',
        *_score_lines(game, high_score, new_high),
        '',
        '[R] Restart',
        '[Q] Quit',
    ]
    draw_centered_box(stdscr, lines)


def _tick_interval(score: int, difficulty: Difficulty | None = None) -> float:
    d = difficulty if difficulty is not None else DIFFICULTIES[DEFAULT_DIFFICULTY_INDEX]
    return max(d.tick_min, d.tick_base - score * d.tick_accel)


def _draw_frame(
    stdscr: curses.window,
    game: Game,
    paused: bool,
    high_score: int,
    new_high: bool,
    use_color: bool = True,
) -> None:
    stdscr.erase()
    stdscr.addstr(0, 2, f' Score: {game.score}   High: {max(high_score, game.score)} ')
    if paused:
        label = ' [ PAUSED ] '
        stdscr.addstr(0, game.screen_width - len(label), label)
    for i, display in enumerate(game.get_displays()):
        attr = curses.color_pair(i + 1) if use_color else curses.A_NORMAL
        for y, x in display:
            stdscr.addstr(y + 1, x, '█', attr)
    if game.game_won:
        draw_win_screen(stdscr, game, high_score, new_high)
    elif game.game_over:
        draw_game_over(stdscr, game, high_score, new_high)
    stdscr.refresh()


def _wait_for_resize(stdscr: curses.window) -> bool:
    """Show a 'terminal too small' message until the window is large enough.
    Returns True when ready to proceed, False if the user presses Q to quit."""
    while True:
        h, w = stdscr.getmaxyx()
        if h >= MIN_LINES and w >= MIN_COLS:
            return True
        _draw_too_small(stdscr)
        stdscr.timeout(-1)
        if _normalize_key(stdscr.getch()) == ord('q'):
            return False


def run(stdscr: curses.window, difficulty_index: int = DEFAULT_DIFFICULTY_INDEX) -> None:
    use_color = curses.has_colors()
    if use_color:
        curses.start_color()
        # Use the terminal's own background (-1) rather than a hardcoded black,
        # so drawn cells match the erased empty cells on any color scheme.
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK
        curses.init_pair(1, curses.COLOR_WHITE, bg)
        curses.init_pair(2, curses.COLOR_CYAN, bg)
        curses.init_pair(3, curses.COLOR_RED, bg)
        curses.init_pair(4, curses.COLOR_GREEN, bg)
    curses.curs_set(False)
    if not _wait_for_resize(stdscr):
        return
    high_score = _load_high_score()
    selected = draw_start_screen(stdscr, high_score, difficulty_index)
    if selected is None:
        return
    difficulty = DIFFICULTIES[selected]
    h, w = stdscr.getmaxyx()
    game = Game(h - 2, w - 1)
    paused = False
    new_high = False
    recorded = False
    prev = time.monotonic() - difficulty.tick_base
    while True:
        delta = _tick_interval(game.score, difficulty)
        if game.game_over or paused:
            stdscr.timeout(PAUSE_POLL_MS)
        else:
            stdscr.timeout(int(max(0, delta - (time.monotonic() - prev)) * 1000))
        ch = _normalize_key(stdscr.getch())
        if ch == ord('q'):
            break
        elif ch == ord('r') and game.game_over:
            selected = draw_start_screen(stdscr, high_score, selected)
            if selected is None:
                break
            difficulty = DIFFICULTIES[selected]
            h, w = stdscr.getmaxyx()
            game = Game(h - 2, w - 1)
            paused = False
            new_high = False
            recorded = False
            prev = time.monotonic() - difficulty.tick_base
        elif ch == ord('p') and not game.game_over:
            paused = not paused
        elif ch == curses.KEY_RESIZE:
            if not _wait_for_resize(stdscr):
                break
            h, w = stdscr.getmaxyx()
            game = Game(h - 2, w - 1)
            paused = False
            new_high = False
            recorded = False
            prev = time.monotonic() - delta
        if not game.game_over and not paused:
            if game.handle_input(ch):
                prev = time.monotonic() - delta
        current = time.monotonic()
        if current - prev >= delta:
            prev = current
            _draw_frame(stdscr, game, paused, high_score, new_high, use_color)
            if not paused:
                game.update()
                if game.game_over and not recorded:
                    recorded = True
                    if game.score > high_score:
                        high_score = game.score
                        new_high = True
                        _save_high_score(high_score)


def _get_version() -> str:
    try:
        return version('snake-game-cli')
    except PackageNotFoundError:
        return 'unknown'


def main() -> None:
    parser = argparse.ArgumentParser(prog='play-snake', description='Play snake in your terminal.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {_get_version()}')
    parser.add_argument(
        '-d',
        '--difficulty',
        choices=DIFFICULTY_NAMES,
        default=DIFFICULTY_NAMES[DEFAULT_DIFFICULTY_INDEX],
        help='Starting difficulty (also selectable on the start screen).',
    )
    args = parser.parse_args()
    wrapper(partial(run, difficulty_index=DIFFICULTY_NAMES.index(args.difficulty)))


if __name__ == '__main__':
    main()
