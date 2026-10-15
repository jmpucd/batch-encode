# batch-encode

Batch-converts MakeMKV rips (Blu-ray / DVD `.mkv`) to H.264 with the English subtitle track burned in.

## Dependencies
- macOS, Python 3 (standard library only, no pip packages)
- `ffmpeg` + `ffprobe` with libx264 (`brew bundle` installs them from the `Brewfile`)
- Bitmap subs (Blu-ray PGS, DVD VobSub — what MakeMKV produces) use ffmpeg's `overlay` filter and work with stock Homebrew ffmpeg.
- Text subs (SRT/ASS) need an ffmpeg built with libass (`subtitles` filter). Check: `ffmpeg -filters | grep subtitles`.

## Setup on a new Mac
    git clone git@github.com:jmpucd/batch-encode.git ~/code/batch-encode
    cd ~/code/batch-encode
    brew bundle
    # edit input_folder / output_folder at the top of batch_encode.py
    python3 batch_encode.py

Set `TEST_SECONDS = 60` in the script to encode just the first minute of each film as a test.

## Update later
    cd ~/code/batch-encode && git pull
