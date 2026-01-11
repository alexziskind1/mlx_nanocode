# mlx_nanocode

Minimal Claude Code alternative with MLX.

## Features

- Full agentic loop with tool use
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
- Conversation history
- Colored terminal output
- Runs locally with mlx-lm

## Usage

### Install mlx-lm:

pip install mlx-lm

### Launch the server:

```bash
mlx_lm.server --model mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-4bit
```

### Run nanocode:

```bash
python nanocode.py
```

## Commands

- `/c` - Clear conversation
- `/q` or `exit` - Quit

## Tools

| Tool | Description |
|------|-------------|
| `read` | Read file with line numbers, offset/limit |
| `write` | Write content to file |
| `edit` | Replace string in file (must be unique) |
| `glob` | Find files by pattern, sorted by mtime |
| `grep` | Search files for regex |
| `bash` | Run shell command |

## Example

```
────────────────────────────────────────
❯ what files are here?
────────────────────────────────────────

⏺ Glob(**/*.py)
  ⎿  nanocode.py

⏺ There's one Python file: nanocode.py
```

## License

MIT
