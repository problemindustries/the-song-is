#!/bin/bash
set -e

CURRENT=$(cat VERSION)
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

echo "Current version: v$CURRENT"
echo ""
echo "  1) major  →  v$((MAJOR+1)).0.0"
echo "  2) minor  →  v$MAJOR.$((MINOR+1)).0"
echo "  3) patch  →  v$MAJOR.$MINOR.$((PATCH+1))"
echo ""
read -p "Bump [1/2/3]: " CHOICE

case $CHOICE in
  1) NEW="$((MAJOR+1)).0.0" ;;
  2) NEW="$MAJOR.$((MINOR+1)).0" ;;
  3) NEW="$MAJOR.$MINOR.$((PATCH+1))" ;;
  *) echo "Invalid choice."; exit 1 ;;
esac

echo "$NEW" > VERSION
echo ""
echo "Releasing v$NEW..."

git add VERSION
git commit -m "Release v$NEW"

git checkout main
git merge dev --no-edit
git push origin main

git tag "v$NEW"
git push origin "v$NEW"

git checkout dev
echo ""
echo "Done. GitHub Actions is building v$NEW."
