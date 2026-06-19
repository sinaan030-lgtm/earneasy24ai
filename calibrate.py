from __future__ import annotations

import time

import pyautogui


def capture_point(label: str) -> tuple[int, int]:
    print()
    print(label)
    input("Hover the mouse there, then press Enter...")
    time.sleep(0.15)
    position = pyautogui.position()
    print(f"Captured: {position.x},{position.y}")
    return position.x, position.y


def region_from_points(
    first: tuple[int, int],
    second: tuple[int, int],
) -> tuple[int, int, int, int]:
    left = min(first[0], second[0])
    top = min(first[1], second[1])
    right = max(first[0], second[0])
    bottom = max(first[1], second[1])
    return left, top, max(1, right - left), max(1, bottom - top)


def format_tuple(values: tuple[int, ...]) -> str:
    return ",".join(str(value) for value in values)


def make_dpi_aware() -> None:
    import sys
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main() -> None:
    make_dpi_aware()
    print("Coordinate calibration (DPI-aware)")
    print("Keep the app/window exactly where you will run the bot.")

    captcha_top_left = capture_point("1. Top-left corner of the CAPTCHA text box")
    captcha_bottom_right = capture_point("2. Bottom-right corner of the CAPTCHA text box")
    input_box = capture_point("3. Center of the answer input field")
    submit_button = capture_point("4. Center of the Submit button")

    calibrate_play = input("Do you want to calibrate the Macro Recorder Play button? (y/n): ").strip().lower()
    if calibrate_play in ("y", "yes"):
        play_button = capture_point("5. Center of the Macro Recorder Play button")
    else:
        play_button = (0, 0)

    capture_region = region_from_points(captcha_top_left, captcha_bottom_right)

    print()
    print("Paste these lines into .env:")
    print(f"CAPTURE_REGION={format_tuple(capture_region)}")
    print(f"INPUT_BOX={format_tuple(input_box)}")
    print(f"SUBMIT_BUTTON={format_tuple(submit_button)}")
    if play_button != (0, 0):
        print(f"PLAY_BUTTON={format_tuple(play_button)}")
    else:
        print("PLAY_BUTTON=0,0")


if __name__ == "__main__":
    main()


