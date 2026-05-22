import curses
import random
import time
from collections import deque
from curses import wrapper
from enum import Enum, auto


class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()


class Element(Enum):
    BORDER = auto()
    SNAKE = auto()
    FOOD = auto()


class Game:
    def __init__(self, screen_height, screen_width):
        random.seed()
        self.game_over = False
        self.height_scale = 1
        self.width_scale = 2
        self.map_height = screen_height // self.height_scale
        self.map_width = screen_width // self.width_scale
        self.screen_height = self.map_height * self.height_scale
        self.screen_width = self.map_width * self.width_scale
        start = (self.map_height // 2, self.map_width // 2)
        self.snake_body = deque([start])
        self.snake_body_set = {start}
        self.snake_length = 5
        self.direction = Direction.UP
        self.score = 0
        self.game_won = False
        self.food = self.get_food()
        self._border_display = self._compute_border()
        self.displays = self.get_displays()

    def _compute_border(self):
        border = []
        for y in range(self.screen_height):
            for x in range(self.screen_width):
                if self.is_border(y // self.height_scale, x // self.width_scale):
                    border.append((y, x))
        return border

    def _to_screen_cells(self, gy, gx):
        return [
            (gy * self.height_scale + dy, gx * self.width_scale + dx)
            for dy in range(self.height_scale)
            for dx in range(self.width_scale)
        ]

    def handle_input(self, ch):
        if ch in (curses.KEY_UP, ord('w')) and self.direction != Direction.DOWN:
            self.direction = Direction.UP
            return True
        if ch in (curses.KEY_DOWN, ord('s')) and self.direction != Direction.UP:
            self.direction = Direction.DOWN
            return True
        if ch in (curses.KEY_LEFT, ord('a')) and self.direction != Direction.RIGHT:
            self.direction = Direction.LEFT
            return True
        if ch in (curses.KEY_RIGHT, ord('d')) and self.direction != Direction.LEFT:
            self.direction = Direction.RIGHT
            return True
        return False

    def update(self):
        if self.game_over:
            return
        y, x = self.get_next_snake_head()
        if self.is_border(y, x) or (y, x) in self.snake_body_set:
            self.game_over = True
            return
        if (y, x) == self.food:
            self.snake_length += 1
            self.score += 1
            self.food = self.get_food()
            if self.food is None:
                self.game_won = True
                self.game_over = True
        self.snake_body.appendleft((y, x))
        self.snake_body_set.add((y, x))
        if self.snake_length < len(self.snake_body):
            removed = self.snake_body.pop()
            self.snake_body_set.discard(removed)
        self.displays = self.get_displays()

    def get_next_snake_head(self):
        y, x = self.snake_body[0]
        if self.direction == Direction.UP:
            return y - 1, x
        elif self.direction == Direction.DOWN:
            return y + 1, x
        elif self.direction == Direction.LEFT:
            return y, x - 1
        elif self.direction == Direction.RIGHT:
            return y, x + 1

    def is_border(self, y, x):
        return y in (0, self.map_height - 1) or x in (0, self.map_width - 1)

    def get_food(self):
        available = (
            {(y, x) for y in range(1, self.map_height - 1) for x in range(1, self.map_width - 1)}
            - self.snake_body_set
        )
        return random.choice(tuple(available)) if available else None

    def get_displays(self):
        snake = [cell for gy, gx in self.snake_body for cell in self._to_screen_cells(gy, gx)]
        food = self._to_screen_cells(*self.food) if self.food else []
        return [self._border_display, snake, food]

    def element(self, y, x):
        if self.is_border(y, x):
            return Element.BORDER
        elif (y, x) in self.snake_body_set:
            return Element.SNAKE
        elif (y, x) == self.food:
            return Element.FOOD
        else:
            return None


def draw_centered_box(stdscr, lines):
    width = max(len(line) for line in lines) + 6
    height = len(lines) + 4
    screen_h, screen_w = stdscr.getmaxyx()
    y0 = (screen_h - height) // 2
    x0 = (screen_w - width) // 2
    stdscr.addstr(y0, x0, '┌' + '─' * (width - 2) + '┐')
    for i in range(1, height - 1):
        stdscr.addstr(y0 + i, x0, '│' + ' ' * (width - 2) + '│')
    try:
        stdscr.addstr(y0 + height - 1, x0, '└' + '─' * (width - 2) + '┘')
    except curses.error:
        pass
    for i, line in enumerate(lines):
        x = x0 + (width - len(line)) // 2
        stdscr.addstr(y0 + 2 + i, x, line)


def draw_start_screen(stdscr):
    lines = [
        "SNAKE  GAME",
        "",
        "↑ / W    Move Up",
        "↓ / S    Move Down",
        "← / A    Move Left",
        "→ / D    Move Right",
        "P        Pause / Resume",
        "Q        Quit",
        "",
        "Press any key to start",
    ]
    stdscr.erase()
    draw_centered_box(stdscr, lines)
    stdscr.refresh()
    stdscr.getch()


def draw_win_screen(stdscr, game):
    lines = [
        "YOU  WIN!",
        f"Score: {game.score}",
        "",
        "[R] Play Again",
        "[Q] Quit",
    ]
    draw_centered_box(stdscr, lines)


def draw_game_over(stdscr, game):
    lines = [
        "GAME  OVER",
        f"Score: {game.score}",
        "",
        "[R] Restart",
        "[Q] Quit",
    ]
    draw_centered_box(stdscr, lines)


def run(stdscr):
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.curs_set(False)
    draw_start_screen(stdscr)
    stdscr.nodelay(True)
    game = Game(curses.LINES - 1, curses.COLS - 1)
    paused = False
    prev = time.monotonic() - 0.2
    while True:
        ch = stdscr.getch()
        if ch == ord('q'):
            break
        elif ch == ord('r') and game.game_over:
            game = Game(curses.LINES - 1, curses.COLS - 1)
            paused = False
            prev = time.monotonic() - 0.2
        elif ch == ord('p') and not game.game_over:
            paused = not paused
        delta = max(0.08, 0.2 - game.score * 0.005)
        if not game.game_over and not paused:
            if game.handle_input(ch):
                prev = time.monotonic() - delta
        current = time.monotonic()
        if current - prev > delta:
            prev = current
            stdscr.erase()
            displays = game.displays
            for i in range(len(displays)):
                for j in range(len(displays[i])):
                    y, x = displays[i][j]
                    stdscr.addstr(y, x, '█', curses.color_pair(i + 1))
            stdscr.addstr(0, 2, f' Score: {game.score} ')
            if paused:
                stdscr.addstr(0, game.screen_width - 11, ' [ PAUSED ] ')
            if game.game_won:
                draw_win_screen(stdscr, game)
            elif game.game_over:
                draw_game_over(stdscr, game)
            stdscr.refresh()
            if not paused:
                game.update()
        time.sleep(0.001)


def main():
    wrapper(run)


if __name__ == '__main__':
    main()
