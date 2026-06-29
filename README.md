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

## Development

Checks run automatically before every `git push` via a tracked `pre-push` hook.
Enable it once after cloning:

```shell
git config core.hooksPath .githooks
```

The hook runs the same checks on your local Python and blocks the push if any fail:

```shell
ruff check .
ruff format --check .
mypy snake_game_cli.py
pytest
```

Bypass it in an emergency with `git push --no-verify`.

On release (pushing a `v*` tag), GitHub Actions runs the test suite across Python
3.10–3.13 and only publishes to PyPI if every version passes.
