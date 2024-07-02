import curses
import random
from curses import wrapper
from datetime import datetime, timedelta
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
        self.snake_body = [(self.map_height // 2, self.map_width // 2)]
        self.snake_length = 5
        self.direction = Direction.UP
        self.food = self.get_food()
        self.displays = self.get_displays()

    def handle_input(self, ch):
        if ch == curses.KEY_UP:
            self.direction = Direction.UP
        elif ch == curses.KEY_DOWN:
            self.direction = Direction.DOWN
        elif ch == curses.KEY_LEFT:
            self.direction = Direction.LEFT
        elif ch == curses.KEY_RIGHT:
            self.direction = Direction.RIGHT

    def update(self):
        if self.game_over:
            return
        y, x = self.get_next_snake_head()
        if self.is_border(y, x) or (y, x) in self.snake_body:
            self.game_over = True
            return
        if (y, x) == self.food:
            self.snake_length += 1
            self.food = self.get_food()
        self.snake_body.insert(0, (y, x))
        if self.snake_length < len(self.snake_body):
            self.snake_body.pop()
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
        food = self.get_random_position()
        while food in self.snake_body:
            food = self.get_random_position()
        return food

    def get_random_position(self):
        return random.randrange(1, self.map_height - 1), random.randrange(1, self.map_width - 1)

    def get_displays(self):
        screen = [[
            self.element(height_index // self.height_scale, width_index // self.width_scale)
            for width_index in range(self.screen_width)]
            for height_index in range(self.screen_height)]
        displays = []
        for element in Element:
            display = []
            for height_index in range(len(screen)):
                for width_index in range(len(screen[height_index])):
                    if element == screen[height_index][width_index]:
                        display.append((height_index, width_index))
            displays.append(display)
        return displays

    def element(self, y, x):
        if self.is_border(y, x):
            return Element.BORDER
        elif (y, x) in self.snake_body:
            return Element.SNAKE
        elif (y, x) == self.food:
            return Element.FOOD
        else:
            return None


def run(stdscr):
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.curs_set(False)
    stdscr.clear()
    stdscr.nodelay(True)
    game = Game(curses.LINES - 1, curses.COLS - 1)
    delta = timedelta(milliseconds=200)
    prev = datetime.now() - delta
    while True:
        ch = stdscr.getch()
        if ch == ord('q'):
            break
        else:
            game.handle_input(ch)
        current = datetime.now()
        if current - prev > delta:
            prev = current
            stdscr.erase()
            displays = game.displays
            for i in range(len(displays)):
                for j in range(len(displays[i])):
                    y, x = displays[i][j]
                    stdscr.addstr(y, x, '█', curses.color_pair(i + 1))
            stdscr.refresh()
            game.update()


def main():
    wrapper(run)


if __name__ == '__main__':
    main()
