# Claude Status Line Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a Python script for Claude Code status bar that displays Git status, context window usage, session cost, and working directory in a two-row format with caching.

**Architecture:** Python script reads JSON session data from stdin, processes information (including cached Git status), and outputs two formatted rows with ANSI colors to stdout. Git information is cached for 5 seconds to improve performance.

**Tech Stack:** Python 3, subprocess (git commands), json, os, sys, datetime

---

## Task 1: Create status line script skeleton

**Files:**
- Create: `~/.claude/statusline.py`

**Step 1: Write the basic script structure**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Status Line
显示 Git 状态、上下文使用、成本和目录信息
"""

import sys
import json
import os
from datetime import datetime


def main():
    """主函数：读取 JSON 并输出状态栏信息"""
    try:
        # 读取 stdin 的 JSON 数据
        data = read_session_data()

        # 获取各模块信息
        git_info = get_git_status()
        context_info = format_context_bar(data)
        cost_info = format_cost(data)
        dir_info = format_directory(data)

        # 输出两行状态信息
        print(format_row1(git_info, context_info))
        print(format_row2(cost_info, dir_info))

    except Exception as e:
        # 错误处理：输出简化状态，不崩溃
        print("-- | --", file=sys.stderr)
        sys.exit(0)


def read_session_data():
    """从 stdin 读取 JSON 数据"""
    import json
    try:
        data = json.load(sys.stdin)
        return data
    except json.JSONDecodeError:
        return {}


if __name__ == "__main__":
    main()
```

**Step 2: Make script executable**

Run: `chmod +x ~/.claude/statusline.py`
Expected: Script becomes executable

**Step 3: Test basic execution**

Run: `echo '{}' | python3 ~/.claude/statusline.py`
Expected: Outputs some text (may have errors for incomplete functions)

**Step 4: Commit**

```bash
git add ~/.claude/statusline.py
git commit -m "feat: add status line script skeleton"
```

---

## Task 2: Implement ANSI color helper function

**Files:**
- Modify: `~/.claude/statusline.py`

**Step 1: Write the color helper function**

After `import` statements, add:

```python
# ANSI 颜色代码
COLORS = {
    'reset': '\033[0m',
    'blue': '\033[34m',
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'white': '\033[37m',
    'gray': '\033[90m',
}


def colorize(text, color):
    """为文本添加 ANSI 颜色"""
    color_code = COLORS.get(color, '')
    reset_code = COLORS['reset']
    return f"{color_code}{text}{reset_code}"
```

**Step 2: Test color function**

Run: `python3 -c "exec(open('~/.claude/statusline.py').read()); print(colorize('Test', 'green'))"`
Expected: Output "Test" in green color

**Step 3: Commit**

```bash
git add ~/.claude/statusline.py
git commit -m "feat: add ANSI color helper function"
```

---

## Task 3: Implement Git status with caching

**Files:**
- Modify: `~/.claude/statusline.py`

**Step 1: Write Git status function with caching**

```python
def get_git_status():
    """获取 git 状态（带 5 秒缓存）"""
    import subprocess
    import time

    cache_file = "/tmp/claude-statusline-git-cache.json"
    cache_ttl = 5  # 5秒缓存

    # 尝试读取缓存
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache = json.load(f)
                if time.time() - cache.get('timestamp', 0) < cache_ttl:
                    return cache
    except (json.JSONDecodeError, IOError):
        pass

    # 获取实际 git 状态
    try:
        # 检查是否在 git 仓库中
        subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            check=True,
            capture_output=True,
            stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {'branch': None, 'staged': 0, 'modified': 0, 'timestamp': 0}

    result = {
        'branch': None,
        'staged': 0,
        'modified': 0,
        'timestamp': time.time()
    }

    try:
        # 获取分支名
        branch = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            check=True,
            capture_output=True,
            text=True
        ).stdout.strip()
        result['branch'] = branch

        # 获取暂存文件数
        staged = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True
        )
        result['staged'] = len([l for l in staged.stdout.split('\n') if l])

        # 获取修改文件数
        modified = subprocess.run(
            ['git', 'diff', '--name-only'],
            capture_output=True,
            text=True
        )
        result['modified'] = len([l for l in modified.stdout.split('\n') if l])

        # 写入缓存
        try:
            with open(cache_file, 'w') as f:
                json.dump(result, f)
        except IOError:
            pass

    except subprocess.CalledProcessError:
        pass

    return result
```

**Step 2: Test Git status function**

Run: `echo '{}' | python3 ~/.claude/statusline.py` (in a git repo)
Expected: No errors, function returns data

**Step 3: Commit**

```bash
git add ~/.claude/statusline.py
git commit -m "feat: implement Git status with caching"
```

---

## Task 4: Implement context bar formatter

**Files:**
- Modify: `~/.claude/statusline.py`

**Step 1: Write context bar function**

```python
def format_context_bar(data):
    """格式化上下文进度条信息"""
    # 获取模型名
    model = data.get('model', {}).get('display_name', 'Unknown')

    # 获取使用百分比
    ctx = data.get('context_window', {})
    used_pct = ctx.get('used_percentage') or 0

    # 确定颜色
    if used_pct < 70:
        color = 'green'
    elif used_pct < 90:
        color = 'yellow'
    else:
        color = 'red'

    # 生成进度条 (10字符)
    filled = int(used_pct / 10)
    bar = '▓' * filled + '░' * (10 - filled)

    return {
        'model': model,
        'bar': bar,
        'percentage': used_pct,
        'color': color
    }
```

**Step 2: Test context bar function**

Run: `echo '{"model":{"display_name":"Opus"},"context_window":{"used_percentage":45}}' | python3 ~/.claude/statusline.py`
Expected: No errors

**Step 3: Commit**

```bash
git add ~/.claude/statusline.py
git commit -m "feat: implement context bar formatter"
```

---

## Task 5: Implement cost formatter

**Files:**
- Modify: `~/.claude/statusline.py`

**Step 1: Write cost formatter function**

```python
def format_cost(data):
    """格式化成本和耗时信息"""
    cost = data.get('cost', {})
    total_cost = cost.get('total_cost_usd') or 0
    api_duration_ms = cost.get('total_api_duration_ms') or 0

    # 格式化成本
    cost_str = f"${total_cost:.4f}"

    # 格式化耗时（转换为秒）
    duration_sec = api_duration_ms / 1000
    duration_str = f"{duration_sec:.0f}s" if duration_sec >= 1 else f"{duration_sec*1000:.0f}ms"

    return {
        'cost': cost_str,
        'duration': duration_str
    }
```

**Step 2: Test cost formatter**

Run: `echo '{"cost":{"total_cost_usd":0.0123456,"total_api_duration_ms":23000}}' | python3 ~/.claude/statusline.py`
Expected: No errors

**Step 3: Commit**

```bash
git add ~/.claude/statusline.py
git commit -m "feat: implement cost formatter"
```

---

## Task 6: Implement directory formatter

**Files:**
- Modify: `~/.claude/statusline.py`

**Step 1: Write directory formatter function**

```python
def format_directory(data):
    """格式化工作目录信息"""
    workspace = data.get('workspace', {})
    current_dir = workspace.get('current_dir') or data.get('cwd') or '.'

    # 将主目录替换为 ~
    home = os.path.expanduser('~')
    if current_dir.startswith(home):
        current_dir = '~' + current_dir[len(home):]

    # 获取项目目录（最后一部分）
    project_name = os.path.basename(current_dir)

    return {
        'full': current_dir,
        'name': project_name
    }
```

**Step 2: Test directory formatter**

Run: `echo '{"workspace":{"current_dir":"/home/user/memory-bank"}}' | python3 ~/.claude/statusline.py`
Expected: No errors

**Step 3: Commit**

```bash
git add ~/.claude/statusline.py
git commit -m "feat: implement directory formatter"
```

---

## Task 7: Implement row formatting functions

**Files:**
- Modify: `~/.claude/statusline.py`

**Step 1: Write row1 formatter (Git + Context)**

```python
def format_row1(git_info, context_info):
    """格式化第一行：Git 状态 + 上下文窗口"""
    # Git 部分
    if git_info.get('branch'):
        branch_str = colorize(f"[{git_info['branch']}]", 'blue')
    else:
        branch_str = colorize('[git:none]', 'gray')

    staged_count = git_info.get('staged', 0)
    modified_count = git_info.get('modified', 0)

    parts = [branch_str]
    if staged_count > 0:
        parts.append(colorize(f"✓{staged_count}", 'green'))
    if modified_count > 0:
        parts.append(colorize(f"~{modified_count}", 'yellow'))

    git_str = ' '.join(parts)

    # 上下文部分
    model_str = colorize(f"[{context_info['model']}]", 'white')
    bar_str = colorize(f"[{context_info['bar']}]", context_info['color'])
    pct_str = colorize(f"{context_info['percentage']}%", context_info['color'])
    context_str = f"{model_str} {bar_str} {pct_str}"

    # 组合
    return f"{git_str} {colorize('|', 'gray')} {context_str}"
```

**Step 2: Write row2 formatter (Cost + Directory)**

```python
def format_row2(cost_info, dir_info):
    """格式化第二行：成本 + 目录"""
    # 成本部分
    cost_str = colorize(f"${cost_info['cost']}", 'green')
    duration_str = colorize(f"({cost_info['duration']})", 'gray')

    # 目录部分
    dir_str = colorize(dir_info['full'], 'white')

    # 组合
    return f"{cost_str} {duration_str} {colorize('|', 'gray')} {dir_str}"
```

**Step 3: Test full output**

Run: `echo '{"model":{"display_name":"Opus"},"context_window":{"used_percentage":45},"cost":{"total_cost_usd":0.0123,"total_api_duration_ms":23000},"workspace":{"current_dir":"/home/myclaw/.openclaw/workspace/memory-bank"}}' | python3 ~/.claude/statusline.py`
Expected: Two rows of formatted output with colors

**Step 4: Commit**

```bash
git add ~/.claude/statusline.py
git commit -m "feat: implement row formatting functions"
```

---

## Task 8: Configure settings.json

**Files:**
- Modify: `~/.claude/settings.json`

**Step 1: Read current settings**

Run: `cat ~/.claude/settings.json`
Expected: Display current settings content

**Step 2: Add statusLine configuration**

If `statusLine` doesn't exist, add it to the JSON. If it exists, update the `command` field.

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py",
    "padding": 1
  }
}
```

**Step 3: Verify settings are valid JSON**

Run: `python3 -m json.tool ~/.claude/settings.json > /dev/null && echo "Valid JSON"`
Expected: "Valid JSON"

**Step 4: Commit settings**

```bash
git add ~/.claude/settings.json
git commit -m "feat: configure status line in settings.json"
```

---

## Task 9: Integration testing

**Step 1: Test with various inputs**

Test 1 - Normal case:
```bash
echo '{"model":{"display_name":"Opus"},"context_window":{"used_percentage":45},"cost":{"total_cost_usd":0.0123,"total_api_duration_ms":23000},"workspace":{"current_dir":"/home/myclaw/.openclaw/workspace/memory-bank"}}' | python3 ~/.claude/statusline.py
```
Expected: Two rows with all info displayed

Test 2 - High context usage:
```bash
echo '{"model":{"display_name":"Opus"},"context_window":{"used_percentage":95},"cost":{},"workspace":{}}' | python3 ~/.claude/statusline.py
```
Expected: Red progress bar

Test 3 - Missing fields:
```bash
echo '{}' | python3 ~/.claude/statusline.py
```
Expected: Graceful fallback with default values

**Step 2: Test cache functionality**

Run script twice quickly in a git repo, observe second call uses cache

**Step 3: Document testing results**

No commit needed - this is verification

---

## Task 10: Final documentation

**Step 1: Create usage documentation**

Create: `~/.claude/statusline-README.md`

```markdown
# Claude Status Line

Custom status line for Claude Code showing Git status, context usage, cost, and directory.

## Installation

Script is at `~/.claude/statusline.py` and configured in `~/.claude/settings.json`.

## Display

**Row 1:** Git status | Context bar
**Row 2:** Cost & Duration | Directory

## Testing

Test with mock input:
```bash
echo '{"model":{"display_name":"Opus"},"context_window":{"used_percentage":45}}' | python3 ~/.claude/statusline.py
```

## Cache

Git information is cached for 5 seconds at `/tmp/claude-statusline-git-cache.json`.
```

**Step 2: Commit documentation**

```bash
git add ~/.claude/statusline-README.md
git commit -m "docs: add status line README"
```
