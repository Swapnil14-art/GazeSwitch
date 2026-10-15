from pynput import keyboard

MODIFIERS = {
    keyboard.Key.ctrl_l: "ctrl",
    keyboard.Key.ctrl_r: "ctrl",
    keyboard.Key.shift_l: "shift",
    keyboard.Key.shift_r: "shift",
    keyboard.Key.alt_l: "alt",
    keyboard.Key.alt_r: "alt",
    keyboard.Key.cmd_l: "cmd",
    keyboard.Key.cmd_r: "cmd",
}


def capture_hotkey(on_complete):
    """
    Capture a hotkey combination from user input.

    Args:
        on_complete: Callback function to call with the captured hotkey.
    """
    pressed_modifiers = set()
    main_key = None

    def on_press(key):
        nonlocal main_key

        if key in MODIFIERS:
            pressed_modifiers.add(MODIFIERS[key])
            return

        # Ignore non-character keys until we get a usable one
        if main_key is None:
            if hasattr(key, "char") and key.char and key.char.isprintable():
                main_key = key
            elif hasattr(key, "name") and key.name:
                main_key = key

    def on_release(key):
        nonlocal main_key

        if key == keyboard.Key.esc:
            listener.stop()
            return

        # Only finalise when the chosen main key is released
        if key != main_key:
            return

        # Must have at least one modifier
        if not pressed_modifiers:
            listener.stop()
            return

        # Resolve key name safely
        if hasattr(main_key, "char") and main_key.char and main_key.char.isprintable():  # type: ignore
            key_name = main_key.char.lower()  # type: ignore
        elif hasattr(main_key, "name") and main_key.name:  # type: ignore
            key_name = f"<{main_key.name}>"  # type: ignore
        else:
            listener.stop()
            return  # invalid main key

        hotkey = "<" + ">+<".join(sorted(pressed_modifiers)) + ">" + f"+{key_name}"
        listener.stop()
        on_complete(hotkey)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
