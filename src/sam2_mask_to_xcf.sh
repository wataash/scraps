#!/bin/sh
# SPDX-FileCopyrightText: Copyright (c) 2026 Wataru Ashihara <wataash0607@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Compose a GIMP mask-editing XCF (photo layer + colored mask layer) from a
# frame image and a binary mask PNG (white = object).
# Inverse of: magick 'NNNN.xcf[1]' -alpha extract -negate NNNN.png
#
# usage: sam2_mask_to_xcf.sh <color-hex> <frame.jpg> <mask.png> <out.xcf>
# e.g.:  sam2_mask_to_xcf.sh 39D3B5 jpg/0250.jpg sam2_mask/0250.png mask_manual_xcf/0250.xcf
set -eu

color="#${1#\#}"
jpg=$(realpath "$2")
mask=$(realpath "$3")
out=$(realpath "$4")

paint=$(mktemp --suffix=.png)
trap 'rm -f "$paint"' EXIT

# solid color with alpha = negate(mask): the painted (opaque) area is the background
magick \( "$mask" -fill "$color" -colorize 100 \) \( "$mask" -negate \) -alpha off -compose CopyOpacity -composite "png32:$paint"

gimp -i --quit --batch-interpreter=plug-in-script-fu-eval -b "
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE \"$jpg\")))
       (paint (car (gimp-file-load-layer RUN-NONINTERACTIVE image \"$paint\"))))
  (gimp-image-insert-layer image paint 0 0)
  (gimp-item-set-name paint \"Layer #1\")
  (gimp-layer-set-opacity paint 31.8)
  (gimp-file-save RUN-NONINTERACTIVE image \"$out\"))"

echo "saved: $out"
