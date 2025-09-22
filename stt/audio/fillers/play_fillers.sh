#!/usr/bin/env bash
# Play all MP3 filler clips in this directory back-to-back.
# Usage: ./play_fillers.sh [player args...]
# If you pass arguments, they replace the default player command.
# Default player: mpg123 -q (quiet). Override by setting PLAYER_CMD env var
# or by providing a command line (e.g. ./play_fillers.sh ffplay -nodisp -autoexit).

set -euo pipefail

cd "$(dirname "$0")"

# Gather the list of mp3 files sorted alphabetically.
shopt -s nullglob
mapfile -t files < <(printf '%s\n' *.mp3 | sort)
if (( ${#files[@]} == 0 )); then
  echo "No MP3 files found in $(pwd)" >&2
  exit 1
fi

# Build the player command: CLI args override env var, which overrides default.
if (( $# > 0 )); then
  player=("$@")
elif [[ -n "${PLAYER_CMD:-}" ]]; then
  # shellcheck disable=SC2206 # Intentional splitting of PLAYER_CMD into words
  player=( ${PLAYER_CMD} )
else
  player=( "mpg123" "-q" )
fi

# Play each file sequentially.
for track in "${files[@]}"; do
  echo "Playing ${track}"
  "${player[@]}" "$track"
  echo "Finished ${track}"$'\n'
done
