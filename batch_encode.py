import os
import subprocess
import json
import shlex
import tempfile

# Set input/output directories
input_folder = "/Users/jmpike/Movies/Process"  # Source files
output_folder = "/Users/jmpike/Movies/Encoded"  # Separate output folder

# Set to a number of seconds to encode only the first N seconds of each film (quick test).
# None = encode the full film.
TEST_SECONDS = None

# Image-based subtitle codecs (Blu-ray PGS, DVD VobSub) must be overlaid, not rendered by libass.
BITMAP_SUB_CODECS = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}

os.makedirs(output_folder, exist_ok=True)


def get_subtitle_tracks(input_file):
    """Return (english_track, forced_track, codecs) using relative subtitle indexes."""
    cmd = ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "s", "-of", "json", input_file]
    result = subprocess.run(cmd, capture_output=True, text=True)

    try:
        streams = json.loads(result.stdout)["streams"]
    except (json.JSONDecodeError, KeyError):
        print(f"Error reading subtitle data for {input_file}")
        return None, None, {}

    english_track = None
    forced_track = None
    codecs = {}

    print("Subtitle tracks found:")
    for idx, stream in enumerate(streams):
        lang = stream.get("tags", {}).get("language", "").lower()
        codec = stream.get("codec_name", "").lower()
        forced = stream.get("disposition", {}).get("forced", 0) == 1
        codecs[idx] = codec
        print(f"  s:{idx}  lang={lang or '?'}  codec={codec}  forced={forced}")

        if "eng" in lang:
            if forced:
                if forced_track is None:
                    forced_track = idx
            elif english_track is None:
                english_track = idx

    return english_track, forced_track, codecs


def process_video(input_path, output_path, sub_track, codec):
    """Encode with the chosen subtitle track burned in."""
    tmp_dir = None
    src = input_path
    bitmap = codec in BITMAP_SUB_CODECS

    if bitmap:
        # PGS / VobSub: overlay the subtitle picture stream onto the video.
        filter_args = ["-filter_complex", f"[0:v:0][0:s:{sub_track}]overlay[v]", "-map", "[v]"]
    else:
        # Text subs: the subtitles filter needs a path with no special characters,
        # so point it at a symlink with a safe name.
        tmp_dir = tempfile.mkdtemp()
        src = os.path.join(tmp_dir, "in.mkv")
        os.symlink(input_path, src)
        filter_args = ["-vf", f"subtitles={src}:si={sub_track}", "-map", "0:v:0"]

    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-stats", "-i", src]
    if TEST_SECONDS:
        cmd += ["-t", str(TEST_SECONDS)]
    cmd += filter_args
    cmd += [
        "-map", "0:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-sn",
        "-y",
        output_path,
    ]

    print("\nFFmpeg command:", " ".join(shlex.quote(str(x)) for x in cmd))

    try:
        # stderr is left attached to the terminal so you see live progress.
        process = subprocess.run(cmd)
        ok = process.returncode == 0
    except Exception as e:
        print(f"Exception while processing {os.path.basename(input_path)}: {e}")
        ok = False
    finally:
        if tmp_dir:
            try:
                os.unlink(src)
                os.rmdir(tmp_dir)
            except OSError:
                pass

    if not ok:
        print(f"Error processing {os.path.basename(input_path)}")
        if os.path.exists(output_path):
            os.unlink(output_path)  # don't leave a partial file behind
    return ok


# Main processing loop
print("Starting batch processing...")
if TEST_SECONDS:
    print(f"TEST MODE: first {TEST_SECONDS} seconds of each film only")
processed_count = 0
skipped_count = 0
error_count = 0

for root, _, files in os.walk(input_folder):
    mkvs = sorted(f for f in files if f.lower().endswith(".mkv") and not f.startswith("."))
    for file in mkvs:
        input_path = os.path.join(root, file)
        stem = os.path.splitext(file)[0]

        # Name the output after the parent folder (the film title). Fall back to the
        # file name if the file sits directly in the input folder or shares its
        # folder with other MKVs, so nothing overwrites anything else.
        folder_name = os.path.basename(root)
        if os.path.abspath(root) == os.path.abspath(input_folder):
            output_filename = f"{stem}.mkv"
        elif len(mkvs) > 1:
            output_filename = f"{folder_name} - {stem}.mkv"
        else:
            output_filename = f"{folder_name}.mkv"
        output_path = os.path.join(output_folder, output_filename)

        print(f"\nProcessing: {file}")
        print(f"Output will be: {output_filename}")

        if os.path.exists(output_path):
            print("Skipping (output already exists)")
            skipped_count += 1
            continue

        english_track, forced_track, codecs = get_subtitle_tracks(input_path)

        # Prefer the full English track; fall back to a forced-only track.
        sub_track = english_track if english_track is not None else forced_track
        if sub_track is None:
            print(f"Skipping {file} (No English subtitles found)")
            error_count += 1
            continue

        print(f"Using subtitle track s:{sub_track} ({codecs[sub_track]})")

        if process_video(input_path, output_path, sub_track, codecs[sub_track]):
            processed_count += 1
            print(f"Successfully processed: {file}")
        else:
            error_count += 1

print("\nBatch processing complete!")
print(f"Successfully processed: {processed_count} files")
print(f"Skipped (already encoded): {skipped_count} files")
print(f"Errors encountered: {error_count} files")
