"""nanocode - minimal claude code alternative"""

import glob as globlib, json, os, re, subprocess, requests

API_URL = "http://localhost:8080/v1/chat/completions"
MODEL = "default_model"

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED, GRAY = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\x1b[90m",
)


# --- Tool implementations ---


def read(args):
    lines = open(args["path"]).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args):
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"


def edit(args):
    text = open(args["path"]).read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = (
        text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    )
    with open(args["path"], "w") as f:
        f.write(replacement)
    return "ok"


def glob(args):
    pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files) or "none"


def grep(args):
    pattern = re.compile(args["pat"])
    hits = []
    for filepath in globlib.glob(args.get("path", ".") + "/**", recursive=True):
        try:
            for line_num, line in enumerate(open(filepath), 1):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except Exception:
            pass
    return "\n".join(hits[:50]) or "none"


def bash(args):
    result = subprocess.run(
        args["cmd"], shell=True, capture_output=True, text=True, timeout=30
    )
    return (result.stdout + result.stderr).strip() or "(empty)"


# --- Tool definitions: (description, schema, function) ---

TOOLS = {
    "read": (
        "Read file with line numbers (file path, not directory)",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file (old must be unique unless all=true)",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit,
    ),
    "glob": (
        "Find files by pattern, sorted by mtime",
        {"pat": "string", "path": "string?"},
        glob,
    ),
    "grep": (
        "Search files for regex pattern",
        {"pat": "string", "path": "string?"},
        grep,
    ),
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
}


def run_tool(name, args):
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def make_schema():
    result = []
    for name, (description, params, _fn) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "number" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        result.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return result


def call_api(messages, system_prompt):
    response = requests.post(
        API_URL,
        json={
            "model": MODEL,
            "max_tokens": 8192,
            "system": system_prompt,
            "messages": messages,
            "tools": make_schema(),
            "tool_choice": "auto",
            "parallel_tool_calls": False,
        },
        headers={
            "Content-Type": "application/json",
        },
    )
    if not response.ok:
        return {"error": f"{response.status_code} {response.text}"}
    try:
        return response.json()
    except json.JSONDecodeError as err:
        return {"error": f"invalid json response: {err}"}


def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def main():
    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} | {os.getcwd()}{RESET}\n")
    messages = []
    system_prompt = (
        "Concise coding assistant. Use tools when needed. "
        "When calling tools, provide arguments as strict JSON with double quotes "
        "and no trailing text. If you cannot provide valid JSON, respond without "
        f"tool calls. cwd: {os.getcwd()}"
    )

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                messages = []
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})

            # agentic loop: keep calling API until no more tool calls
            while True:
                response = call_api(messages, system_prompt)
                if error := response.get("error"):
                    print(f"\n{RED}⏺ API Error: {error}{RESET}")
                    break
                block = response.get("choices", [{}])[0].get("message", [])
                tool_result = ""

                if reasoning := block.get("reasoning", False):
                    print(f"\n{GRAY}{render_markdown(reasoning)}{RESET}")
                if content := block.get("content", "").strip():
                    print(f"\n{CYAN}⏺{RESET} {render_markdown(content)}")

                tool_calls = block.get("tool_calls")
                if tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": block.get("content"),
                            "tool_calls": tool_calls,
                        }
                    )
                    for tool_call in tool_calls:
                        tool = tool_call.get("function", {})
                        tool_name = tool.get("name", "unknown")
                        tool_args = tool.get("arguments", "")
                        arg_preview = (
                            tool_args[:50] if isinstance(tool_args, str) else str(tool_args)[:50]
                        )
                        print(
                            f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                        )

                        try:
                            parsed_args = (
                                json.loads(tool_args)
                                if isinstance(tool_args, str)
                                else tool_args
                            )
                        except json.JSONDecodeError as err:
                            result = f"error: invalid tool arguments ({err})"
                        else:
                            result = run_tool(tool_name, parsed_args)

                        result_lines = result.split("\n")
                        preview = result_lines[0][:60]
                        if len(result_lines) > 1:
                            preview += f" ... +{len(result_lines) - 1} lines"
                        elif len(result_lines[0]) > 60:
                            preview += "..."
                        print(f"  {DIM}⎿  {preview}{RESET}")

                        tool_result = result
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.get("id"),
                                "content": tool_result,
                            }
                        )

                else:
                    messages.append({"role": "assistant", "content": block.get("content", "")})
                    break

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()
