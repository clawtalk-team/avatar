#!/usr/bin/env bash
# ── publish-avatars.sh ─────────────────────────────────────────────────────────
#
# Upload generated avatar heads to the S3 bucket behind avatars.voxhelm.com.
#
# Usage:
#   ./scripts/publish-avatars.sh                  # publish all heads
#   ./scripts/publish-avatars.sh young_woman      # publish specific head(s)
#   ./scripts/publish-avatars.sh --dry-run        # preview what would be uploaded
#
# Prerequisites:
#   - AWS CLI configured with profile 'personal'
#   - Heads generated in outputs/heads/
#
# S3 layout:
#   s3://avatars-voxhelm-com/heads/{name}/sil.png
#   s3://avatars-voxhelm-com/heads/{name}/PP.png
#   s3://avatars-voxhelm-com/heads/{name}/...
#   s3://avatars-voxhelm-com/heads/manifest.json
#
# CDN URL:
#   https://avatars.voxhelm.com/heads/{name}/sil.png
#   https://avatars.voxhelm.com/heads/manifest.json

set -euo pipefail

BUCKET="avatars-voxhelm-com"
PROFILE="personal"
HEADS_DIR="outputs/heads"
DISTRIBUTION_COMMENT="avatars.voxhelm.com"
DRY_RUN=""
HEADS=()

# Parse args
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN="--dryrun" ;;
    --help|-h)
      echo "Usage: $0 [--dry-run] [head_name ...]"
      echo ""
      echo "Publish avatar heads to s3://$BUCKET"
      echo "Without arguments, publishes all heads in $HEADS_DIR/"
      exit 0
      ;;
    *) HEADS+=("$arg") ;;
  esac
done

# Change to repo root
cd "$(dirname "$0")/.."

if [ ! -d "$HEADS_DIR" ]; then
  echo "Error: $HEADS_DIR not found. Generate heads first with 'voxhelm generate'."
  exit 1
fi

# If no specific heads given, publish all
if [ ${#HEADS[@]} -eq 0 ]; then
  for d in "$HEADS_DIR"/*/; do
    HEADS+=("$(basename "$d")")
  done
fi

echo "Publishing ${#HEADS[@]} head(s) to s3://$BUCKET"
echo ""

TOTAL_FILES=0

for head in "${HEADS[@]}"; do
  head_dir="$HEADS_DIR/$head"
  if [ ! -d "$head_dir" ]; then
    echo "  SKIP $head — directory not found"
    continue
  fi

  # Count viseme files
  file_count=$(find "$head_dir" -maxdepth 1 \( -name "*.png" -o -name "*.svg" \) | wc -l | tr -d ' ')
  echo "  $head — $file_count files"

  # Sync viseme files (png/svg only, skip gallery.html, cost.json, etc.)
  aws s3 sync "$head_dir" "s3://$BUCKET/heads/$head/" \
    --profile "$PROFILE" \
    --exclude "*" \
    --include "*.png" \
    --include "*.svg" \
    $DRY_RUN

  TOTAL_FILES=$((TOTAL_FILES + file_count))
done

echo ""

# Generate and upload manifest.json
if [ -z "$DRY_RUN" ]; then
  echo "Generating manifest.json..."
  manifest_file=$(mktemp)

  python3 -c "
import json
from pathlib import Path

heads_dir = Path('$HEADS_DIR')
manifest = {'heads': []}

for d in sorted(heads_dir.iterdir()):
    if not d.is_dir():
        continue
    meta_path = d / '.voxhelm.json'
    if not meta_path.exists():
        continue
    meta = json.loads(meta_path.read_text())
    ext = 'svg' if (d / 'sil.svg').exists() else 'png'
    visemes = [f.stem for f in d.glob(f'*.{ext}')
               if f.stem not in ('base', 'blink', 'brows_up', '_neutral')]
    extras = [f.stem for f in d.glob(f'*.{ext}')
              if f.stem in ('blink', 'brows_up')]
    anims = [f.stem for f in (d / 'anim').glob('*.mp4')] if (d / 'anim').exists() else []

    manifest['heads'].append({
        'name': d.name,
        'mode': meta.get('mode', 'photo'),
        'style': meta.get('style', ''),
        'ext': ext,
        'visemes': len(visemes),
        'extras': extras,
        'animations': sorted(anims),
    })

print(json.dumps(manifest, indent=2))
" > "$manifest_file"

  aws s3 cp "$manifest_file" "s3://$BUCKET/heads/manifest.json" \
    --profile "$PROFILE" \
    --content-type "application/json"

  rm "$manifest_file"
  echo "  manifest.json uploaded ($(python3 -c "import json; m=json.load(open('$HEADS_DIR/../heads/manifest.json' if False else '/dev/stdin')); print(len(m['heads']))" < /dev/null 2>/dev/null || echo "${#HEADS[@]}") heads)"
fi

echo ""
echo "Done! $TOTAL_FILES files published."
echo ""
echo "CDN URL: https://avatars.voxhelm.com/heads/"
echo "Example: https://avatars.voxhelm.com/heads/friendly_robot/sil.png"

# Invalidate CloudFront cache if not dry run
if [ -z "$DRY_RUN" ]; then
  echo ""
  echo "Invalidating CloudFront cache..."
  DIST_ID=$(aws cloudfront list-distributions --profile "$PROFILE" \
    --query "DistributionList.Items[?contains(Comment,'avatars.voxhelm.com')].Id" \
    --output text 2>/dev/null || echo "")

  if [ -n "$DIST_ID" ] && [ "$DIST_ID" != "None" ]; then
    aws cloudfront create-invalidation \
      --profile "$PROFILE" \
      --distribution-id "$DIST_ID" \
      --paths "/heads/*" \
      --output text > /dev/null
    echo "  Invalidation created for distribution $DIST_ID"
  else
    echo "  CloudFront distribution not found — deploy terraform first"
  fi
fi
