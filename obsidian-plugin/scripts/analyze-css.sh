#!/bin/bash
# CSS Analysis Script for Arete Obsidian Plugin
# Generates mapping of CSS classes: where defined vs where used

set -e
cd "$(dirname "$0")/.."

echo "=== CSS CLASS ANALYSIS ==="
echo ""

# 1. Extract all unique CSS class definitions from source CSS files
echo "## CSS Classes Defined in Source Files"
echo ""

CSS_FILES=(
    "src/styles/base.css"
    "src/styles/gutter.css"
    "src/styles/CardGutter.css"
    "src/styles/yaml-editor.css"
    "src/styles/dashboard.css"
    "src/styles/chat.css"
    "src/styles/styles.css"
)

for file in "${CSS_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "### $file"
        # Extract class names (patterns like .class-name)
        grep -oE '\.[a-zA-Z][a-zA-Z0-9_-]*' "$file" 2>/dev/null | \
            sed 's/^\.//' | \
            sort | uniq | \
            while read class; do
                echo "  - $class"
            done
        echo ""
    fi
done

echo ""
echo "## CSS Classes Used in TypeScript Files"
echo ""

# 2. Extract CSS classes referenced in TypeScript
grep -rhoE "arete-[a-zA-Z0-9-]+" src/ --include="*.ts" 2>/dev/null | \
    sort | uniq -c | sort -rn | \
    while read count class; do
        echo "  $count x $class"
    done

echo ""
echo "## Potential Duplicates (classes defined in multiple CSS files)"
echo ""

# 3. Find classes defined in multiple files
declare -A class_files
for file in "${CSS_FILES[@]}"; do
    if [ -f "$file" ]; then
        for class in $(grep -oE '\.[a-zA-Z][a-zA-Z0-9_-]*' "$file" 2>/dev/null | sed 's/^\.//' | sort | uniq); do
            if [ -n "${class_files[$class]}" ]; then
                class_files[$class]="${class_files[$class]}, $file"
            else
                class_files[$class]="$file"
            fi
        done
    fi
done

for class in "${!class_files[@]}"; do
    files="${class_files[$class]}"
    if [[ "$files" == *","* ]]; then
        echo "  - $class:"
        echo "    Defined in: $files"
    fi
done

echo ""
echo "## Unused CSS Classes (defined but not referenced in TS)"
echo ""

# Get all classes used in TS
ts_classes=$(grep -rhoE "arete-[a-zA-Z0-9-]+" src/ --include="*.ts" 2>/dev/null | sort | uniq)

for file in "${CSS_FILES[@]}"; do
    if [ -f "$file" ]; then
        for class in $(grep -oE '\.arete-[a-zA-Z0-9_-]*' "$file" 2>/dev/null | sed 's/^\.//' | sort | uniq); do
            if ! echo "$ts_classes" | grep -q "^${class}$"; then
                echo "  - $class (in $file)"
            fi
        done
    fi
done
