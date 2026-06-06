#!/bin/bash
set -e

echo "Merging dev → main..."
git checkout main
git merge dev --no-edit
git push origin main
git checkout dev
echo "Done. GitHub Actions will build and publish the release."
