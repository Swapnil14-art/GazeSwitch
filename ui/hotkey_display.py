DISPLAY_NAMES = {
    "ctrl": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "cmd": "Cmd",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
    "enter": "Enter",
    "esc": "Esc",
    "tab": "Tab",
    "space": "Space",
    "backspace": "Backspace",
    "delete": "Delete",
    "insert": "Insert",
    "home": "Home",
    "end": "End",
    "pageup": "Page Up",
    "pagedown": "Page Down",
    "up": "↑",
    "down": "↓",
    "left": "←",
    "right": "→",
    "`": "`",
    "-": "-",
    "=": "=",
    "[": "[",
    "]": "]",
    "\\": "\\",
    ";": ";",
    "'": "'",
    ",": ",",
    ".": ".",
    "/": "/",
    "num0": "Num0",
    "num1": "Num1",
    "num2": "Num2",
    "num3": "Num3",
    "num4": "Num4",
    "num5": "Num5",
    "num6": "Num6",
    "num7": "Num7",
    "num8": "Num8",
    "num9": "Num9",
    "num+": "Num +",
    "num-": "Num -",
    "num*": "Num *",
    "num/": "Num /",
    "num.": "Num .",
}


def format_hotkey_for_display(hotkey: str) -> str:
    """
    Convert a stored hotkey string like '<alt>+\\' into a user-friendly
    display string like 'Alt + \'.

    Args:
        hotkey (str): The raw hotkey string to format.

    Returns:
        str: The hotkey formatted in a user-friendly form.
    """
    parts = hotkey.replace("<", "").replace(">", "").split("+")
    formatted = []
    for part in parts:
        formatted.append(DISPLAY_NAMES.get(part.lower(), part.upper()))
    return " + ".join(formatted)
