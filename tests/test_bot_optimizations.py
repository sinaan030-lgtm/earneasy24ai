import sys
import types

sys.modules.setdefault("pyautogui", types.SimpleNamespace(
    screenshot=lambda *args, **kwargs: None,
    PAUSE=0.0,
    FAILSAFE=False,
    click=lambda *args, **kwargs: None,
    hotkey=lambda *args, **kwargs: None,
    press=lambda *args, **kwargs: None,
    pixel=lambda *args, **kwargs: (0, 0, 0),
    position=lambda: types.SimpleNamespace(x=0, y=0),
))
sys.modules.setdefault("keyboard", types.SimpleNamespace(add_hotkey=lambda *args, **kwargs: None, wait=lambda: None))
sys.modules.setdefault("pyperclip", types.SimpleNamespace(copy=lambda *args, **kwargs: None, paste=lambda *args, **kwargs: ""))

import importlib
import sys
import types

from PIL import Image

from bot import _detect_captcha_presence, capture_screen, duplicate_key


def test_capture_screen_falls_back_for_pyautogui_versions_without_pause_kwarg():
    class CompatPyAutoGUI:
        def screenshot(self, *args, **kwargs):
            if "_pause" in kwargs:
                raise TypeError("unexpected keyword argument '_pause'")
            return "ok"

    import bot

    bot.pyautogui = CompatPyAutoGUI()
    assert capture_screen(type("Config", (), {"capture_region": (0, 0, 1, 1)})()) == "ok"


def test_import_is_resilient_when_optional_gui_modules_are_missing():
    sys.modules.pop("bot", None)

    original_pyautogui = sys.modules.get("pyautogui")
    original_keyboard = sys.modules.get("keyboard")
    original_pyperclip = sys.modules.get("pyperclip")

    sys.modules["pyautogui"] = None
    sys.modules["keyboard"] = None
    sys.modules["pyperclip"] = None

    try:
        imported_bot = importlib.import_module("bot")
    finally:
        if original_pyautogui is None:
            sys.modules.pop("pyautogui", None)
        else:
            sys.modules["pyautogui"] = original_pyautogui
        if original_keyboard is None:
            sys.modules.pop("keyboard", None)
        else:
            sys.modules["keyboard"] = original_keyboard
        if original_pyperclip is None:
            sys.modules.pop("pyperclip", None)
        else:
            sys.modules["pyperclip"] = original_pyperclip

    assert hasattr(imported_bot, "capture_screen")


def test_detect_captcha_presence_rejects_blank_image():
    blank = Image.new("RGB", (100, 100), color=(255, 255, 255))
    assert _detect_captcha_presence(blank) is False


def test_detect_captcha_presence_accepts_text_like_image():
    image = Image.new("RGB", (100, 100), color=(255, 255, 255))
    for x in range(10, 90):
        image.putpixel((x, 50), (0, 0, 0))
    assert _detect_captcha_presence(image) is True


def test_duplicate_key_normalizes_whitespace_and_case():
    assert duplicate_key("  Ab  C  ") == "abc"
