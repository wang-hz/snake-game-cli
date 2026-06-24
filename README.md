# snake-game-cli

Play snake game in your terminal.

![demo](https://raw.githubusercontent.com/wang-hz/snake-game-cli/main/demo.svg)

## Installation

```shell
pip install snake-game-cli
```

## Usage

```shell
play-snake                 # start at Normal difficulty
play-snake -d hard         # or easy / normal / hard
```

You can also pick the difficulty on the start screen with `←` / `→`, then press `Enter` to begin.

## Controls

| Key | Action |
|-----|--------|
| `↑` / `W` | Move up |
| `↓` / `S` | Move down |
| `←` / `A` | Move left |
| `→` / `D` | Move right |
| `P` | Pause / Resume |
| `Q` | Quit |

On the start screen, `←` / `→` change the difficulty and `Enter` starts the game.

## Features

- Three difficulty presets (easy / normal / hard), selectable via `-d` or on the start screen
- Restarting after game over returns to the difficulty selector, so you can switch presets between runs
- Snake speeds up as your score increases
- High score persists across sessions
- Pressing a direction key triggers an immediate move
- Terminal resize is handled gracefully
