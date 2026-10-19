#!/bin/sh
# Record real Emacs frames and encode the looping README GIF.
set -eu

cd "$(dirname "$0")/.."
emacs_bin=${EMACS:-emacs}
command -v "$emacs_bin" >/dev/null
command -v ffmpeg >/dev/null
: "${DISPLAY:?The demo needs an X display; run in a graphical session or under xvfb-run}"
frames_dir=$(mktemp -d "${TMPDIR:-/tmp}/markdown-modern-demo.XXXXXX")
trap 'rm -rf "$frames_dir"' EXIT
trap 'exit 1' HUP INT TERM

# Create the frame from a private daemon so its focus flags apply before it
# appears.  A normal Emacs startup window could intercept the user's typing.
# Bypass window-manager tiling so the recording keeps its requested dimensions.
MARKDOWN_MODERN_DEMO_FRAMES="$frames_dir" \
    "$emacs_bin" -Q --fg-daemon="markdown-modern-demo-$$" -L lisp \
    --eval '(progn
      (select-frame (make-frame-on-display (getenv "DISPLAY")
        (quote ((no-focus-on-map . t) (no-accept-focus . t)
                (override-redirect . t)))))
      (load (expand-file-name "scripts/demo.el") nil t t))'
ffmpeg -hide_banner -loglevel warning -y \
    -f concat -safe 0 -i "$frames_dir/frames.ffconcat" \
    -filter_complex \
    'fps=20,split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=bayer:bayer_scale=3' \
    -loop 0 "$frames_dir/demo.gif"
mv "$frames_dir/demo.gif" images/demo.gif
printf 'Recorded images/demo.gif\n'
