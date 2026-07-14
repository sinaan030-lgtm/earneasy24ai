# earneasy24ai

Fully automated screen OCR submitter. It watches a configured screen region,
detects pixel changes, reads text with EasyOCR first, optionally falls back to
the NVIDIA vision API, cleans the text, pastes it into the configured input box,
and clicks submit.

## Install

```powershell
python -m pip install -r requirements.txt
```

## Configure

Copy `.env.example` to `.env` and adjust the values.

```env
CAPTURE_REGION=700,193,478,205
INPUT_BOX=100,325
SUBMIT_BUTTON=200,400

OCR_MODE=accurate
NVIDIA_API_KEY=

DUPLICATE_TEXT_WINDOW_SECONDS=10.0
```

OCR modes:

- `accurate`: EasyOCR first, then NVIDIA verification when an API key is set.
- `hybrid`: EasyOCR first, NVIDIA fallback only when EasyOCR returns nothing.
- `easyocr`: EasyOCR only.
- `nvidia`: NVIDIA OCR model for every processed screenshot.

For NVIDIA OCR, use `NVIDIA_MODEL=nvidia/nemotron-ocr-v2`.

## Calibrate

Run this first whenever the window moves or your screen resolution changes:

```powershell
python calibrate.py
```

It captures the CAPTCHA box, input field, and Submit button coordinates, then
prints the exact `.env` lines to use.

## Run

You can run the bot in either GUI mode (recommended) or CLI terminal mode.

### GUI Mode (Recommended)
Launch the visual control panel (styled like Macro Recorder):
```powershell
python gui.py
```
**Features:**
- **Toolbar:** Click **Play** to start, **Stop** to stop, or calibrate visually.
- **Visual Snipping:** Click **Region** to open a semi-transparent screen overlay, then click and drag a rectangle over the CAPTCHA area.
- **Click Calibration:** Click **Input**, **Submit**, or **Play Btn** to select coordinates directly by clicking on your screen.
- **Live Action Log:** View detections and coordinate updates in real time.
- **Config Editor:** Adjust delays, confidence levels, and API credentials from the settings sidebar and save directly to `.env`.

### CLI Mode
To run inside the terminal:
```powershell
python bot.py
```

---

## Hotkeys

Global hotkeys work in both CLI and GUI modes:
- `F6`: Set input box to the current mouse position
- `F7`: Set submit button to the current mouse position
- `F10`: Set play button (for Macro Recorder) to the current mouse position
- `F8`: Start the bot
- `F9`: Stop the bot
- `F12`: Print the current mouse/config positions

