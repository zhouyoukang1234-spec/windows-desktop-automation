# Windows Desktop Automation Rules

## STARTUP (Required before any operation)

```
Start-Process python -ArgumentList "v2_simplified\monitor.py" -WindowStyle Hidden
Start-Process python -ArgumentList "v2_simplified\vision_monitor.py","--interval","0.5" -WindowStyle Hidden
Start-Process python -ArgumentList "v2_simplified\app_monitor.py","--daemon" -WindowStyle Hidden
```

Wait 2s, then verify: `read_file v2_simplified/output/latest.json`

If JSON not readable → check .gitignore, add exception for output/*.json

---

## DATA FILES

- `v2_simplified/output/latest.json` - UIA controls (primary)
- `v2_simplified/output/latest.png` - Screenshot
- `v2_simplified/output/latest_vision.json` - Vision OCR (fallback)
- `v2_simplified/output/apps.json` - Running apps

---

## WORKFLOW

1. **READ FULL JSON** - Use `read_file` to see ALL controls, not just grep
2. **GET COORDINATES** - From JSON only, NEVER guess
3. **ONE ACTION** - `python -c "import pyautogui; pyautogui.click(X,Y)"`
4. **VERIFY** - `read_file latest.png` to confirm result
5. **IF FAILED** - Change method, don't repeat same action

---

## APP SWITCHING (apps.json)

```python
# Taskbar app
python -c "from ctypes import windll; windll.user32.SetForegroundWindow(HWND)"

# Background QQ
python -c "import pyautogui; pyautogui.hotkey('ctrl','alt','z')"

# Background WeChat  
python -c "import pyautogui; pyautogui.hotkey('ctrl','alt','w')"

# Launch new app
python -c "import os; os.system('start chrome')"
```

---

## TEXT INPUT

```python
# Chinese text (clipboard method)
python -c "import pyperclip; pyperclip.copy('文字'); import pyautogui; pyautogui.hotkey('ctrl','v')"

# Keys
python -c "import pyautogui; pyautogui.press('enter')"
```

---

## RULES

1. **NO GUESSING** - All coordinates from JSON
2. **NO BLIND CLICKS** - Verify screen state first
3. **NO BATCH OPS** - One action per command
4. **NO MCP CLICKS** - Coordinate system mismatch
5. **NO REPEATED FAILURES** - Change approach after 2 fails
6. **READ FULL JSON** - Don't rely only on grep
7. **FIX GITIGNORE FIRST** - If JSON not readable
