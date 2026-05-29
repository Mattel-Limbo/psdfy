# Plan: Lightweight Install Mode (GroundingDINO only, no SAM2)

> Audience: junior dev / cheap AI model.
> Goal: when user installs `psdfy` **without SAM2 weights**, the conversion UI must
> only offer **GroundingDINO mode** (no SAM2 option visible). The combined
> "GroundingDINO + SAM2" experience stays as it is. A new "both" feature is for later.
>
> Scope of THIS update: only the **conversion option** (the mode dropdown in the UI
> + the matching backend route) needs to react to the install state. Do not build
> the "both" feature yet.

---

## 1. Background (what already exists)

Files you must read before touching anything:

- `psdfy/commands/install.py` — has `--no-weights` flag, already writes
  `enable_sam2` to config.
- `psdfy/config.py:38` — `create_default_config(... enable_sam2: bool = True)`
  writes `[models] enable_sam2 = ...` and `enable_grounding_dino = false`.
- `psdfy/weights.py` — only downloads SAM2 today. GroundingDINO entry exists in
  `MODELS` dict but is never called.
- `app/services/segmenter.py` — `segment_auto()` uses SAM2,
  `segment_with_prompt()` currently **falls back to `segment_auto`** (TODO line 131).
- `app/models/dino_loader.py` — GroundingDINO loader exists but is broken
  (missing `import torch`, references config it does not ship).
- `app/api_app/routes/convert.py:81` — only accepts `mode in ("auto", "prompt")`.
- `app/web/templates/app.html:251-254` — mode dropdown is hardcoded with two
  options: `auto` and `prompt`.
- `app/schemas/convert.py:11` — `mode` field comment says `'auto' or 'prompt'`.

---

## 2. End state (what the user will see)

Two install paths:

| Install command            | SAM2 weights | DINO weights | UI mode dropdown shows                |
| -------------------------- | ------------ | ------------ | ------------------------------------- |
| `psdfy install`            | yes          | yes          | `Otomatis (SAM 2)`, `Text Prompt`      |
| `psdfy install --no-weights` | **no**       | yes          | `Text Prompt (GroundingDINO)` only     |

Behavior when SAM2 is unavailable:

- The "Otomatis (SAM 2)" option is hidden in the UI.
- The default selected mode becomes `prompt`.
- Backend rejects `mode=auto` with a clear error.
- Backend `mode=prompt` runs **GroundingDINO only** (returns bbox rectangles as
  masks — no SAM2 refinement).

---

## 3. Step-by-step tasks

Do them in this order. Each step is small and testable.

### Step 1 — Install command: split weights

File: `psdfy/commands/install.py`

- When `--no-weights` is passed, **still download GroundingDINO weights**.
  Only skip SAM2.
- After Step 3 in the existing flow, add another block:
  - Always download `groundingdino` (using existing `WeightsDownloader.download_model("groundingdino", ...)`).
  - On failure, print warning but do not stop install.
- Keep the SAM2 download wrapped in `if not no_weights:` (already done).

### Step 2 — Config: persist capability flags

File: `psdfy/config.py`

- In `create_default_config`, set:
  - `enable_sam2 = not no_weights` (already correct via caller).
  - `enable_grounding_dino = true` (change current hardcoded `false` on line 91).
- That is the only change needed in this file.

### Step 3 — Backend settings: read the flags

File: `app/core/config.py` (read it first to find the `Settings` class).

- Add two settings sourced from `~/.psdfy/config.toml` `[models]` section:
  - `ENABLE_SAM2: bool` (default `True`)
  - `ENABLE_GROUNDING_DINO: bool` (default `False`)
- Wire them through whatever loader the project already uses.

### Step 4 — Capabilities endpoint (UI needs this)

File: `app/api_app/routes/convert.py` (or a new `capabilities.py` route file).

- Add `GET /capabilities` returning JSON:
  ```json
  {
    "modes": ["prompt"],          // include "auto" only if ENABLE_SAM2
    "default_mode": "prompt",
    "sam2_available": false,
    "dino_available": true
  }
  ```
- Logic:
  - If `ENABLE_SAM2` and SAM2 weights file exists → include `"auto"` in modes.
  - If `ENABLE_GROUNDING_DINO` and DINO weights file exists → include `"prompt"`.
  - `default_mode` = `"auto"` if available, else `"prompt"`.
- Register the route in `app/api_app/factory.py`.

### Step 5 — Backend: implement DINO-only segmentation

File: `app/services/segmenter.py`

- Fix the existing TODO on line 131. Replace the body of
  `segment_with_prompt` so it:
  1. Loads GroundingDINO via `get_grounding_dino_loader()`.
  2. Runs DINO with the user prompt to get bounding boxes + labels.
  3. For each bbox, build a **rectangular boolean mask** (filled rectangle
     inside the bbox, zeros elsewhere). This is the "DINO only" output.
  4. Wrap each as a `Mask(mask=..., bbox=..., area=..., score=..., label=...)`.
- Do **not** call SAM2 in this path. SAM2 refinement is the "both" feature for later.

File: `app/models/dino_loader.py`

- Fix the bugs blocking import:
  - Add `import torch` at the top.
  - Make the `config_file` path absolute (resolve from the installed
    `groundingdino` package dir, do not hardcode a relative path).
  - Wrap heavy imports (`torch`, `groundingdino`) inside the `load()` method
    so the module imports cleanly even when DINO is not installed.

### Step 6 — Backend: gate the convert route

File: `app/api_app/routes/convert.py`

- At line 81 (`if mode not in ("auto", "prompt")`):
  - If `mode == "auto"` and SAM2 is unavailable → raise `InvalidImageError`
    with message `"SAM 2 is not installed. Use mode='prompt' or run 'psdfy install' (full)."`.
  - If `mode == "prompt"` and DINO is unavailable → similar error.
- Use the same availability check as Step 4 (extract a small helper
  `get_capabilities()` and reuse).

### Step 7 — UI: dynamic mode dropdown

File: `app/web/templates/app.html`

- On page load, before showing the convert form:
  - `fetch('/api/capabilities')` (route through whatever the existing UI
    proxy is — check `app/ui_app/routes/proxy.py`).
  - Build the `<select id="modeSelect">` options dynamically:
    - If `sam2_available` → add `<option value="auto">Otomatis (SAM 2)</option>`.
    - If `dino_available` → add `<option value="prompt">Text Prompt (GroundingDINO)</option>`.
  - Set `select.value = data.default_mode`.
  - If only `prompt` is available, also auto-show the `#promptDiv`
    (currently controlled by the `change` listener on line 349) and
    keep the prompt input required.
- If both are unavailable, show a banner: "No models installed. Run
  `psdfy install` first." and disable the convert button.

### Step 8 — Schema + validation

File: `app/schemas/convert.py:11`

- Update the docstring/comment on `mode` to reflect that allowed values
  depend on installed models. Keep the type as `str`.

### Step 9 — Tests

Folder: `tests/`

- Add `tests/test_capabilities.py`:
  - Patches settings to simulate `ENABLE_SAM2 = False` and asserts
    `/capabilities` returns only `["prompt"]`.
- Add `tests/test_install_no_weights.py`:
  - Runs `install_command(no_weights=True, dry_run=False)` against a temp
    config dir, asserts:
    - SAM2 file was **not** downloaded.
    - DINO file was downloaded (mock `WeightsDownloader.download_model`).
    - `config.toml` has `enable_sam2 = false` and `enable_grounding_dino = true`.
- Add `tests/test_segmenter_dino_only.py`:
  - Mocks DINO loader to return fixed bboxes.
  - Asserts `segment_with_prompt` returns rectangular masks at those bboxes
    and never touches SAM2.

### Step 10 — Docs

File: `README.md`

- Add a "Lightweight install" subsection:
  - `psdfy install --no-weights` → only GroundingDINO (text-prompt mode).
  - Note that "Auto" mode requires the full install.
  - Mention "both" mode is coming soon.

---

## 4. Definition of done

- [ ] `psdfy install --no-weights` finishes without downloading SAM2.
- [ ] After that install, opening the UI shows **only** the GroundingDINO option.
- [ ] Submitting a conversion with a text prompt produces a PSD using
      DINO bboxes as rectangular layer masks.
- [ ] `GET /capabilities` reflects the install state.
- [ ] All tests in `tests/` pass.
- [ ] README updated.

---

## 5. Out of scope (do NOT build now)

- SAM2 + GroundingDINO combined refinement ("both" mode).
- Any UI redesign beyond hiding/showing the dropdown option.
- Migrations for users who already installed before this change (a fresh
  `psdfy install` is acceptable).
