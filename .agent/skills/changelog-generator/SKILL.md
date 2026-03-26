---
name: changelog-generator
description: Automatically generate polished, user-friendly changelogs from Git commits. Transforms technical commit messages into clear, categorized release notes suitable for customers or stakeholders.
license: MIT
---

# Changelog Generator

## Overview
Automate the creation of high-quality changelogs. This skill analyzes git history and produces structured, readable release notes.

## Usage
Run this skill from the root of a Git repository to generate a `CHANGELOG.md` or update an existing one.

## Features
- **Categorization**: Groups changes into:
    - 🚀 **New Features**
    - 🐛 **Bug Fixes**
    - ⚡ **Performance Improvements**
    - 🔒 **Security Updates**
    - 🚮 **Deprecated/Removed**
    - 🔧 **Internal/Refactoring** (often excluded from public notes)
- **Translation**: Rewrites technical commit messages (e.g., "fix(auth): correct jwt verification logic") into user-facing text (e.g., "Fixed an issue where some users could not log in securely").
- **Formatting**: Output is standard Markdown, ready to be pasted into GitHub Releases or documentation.

## Workflow
1. **Analyze History**: Look at commits since the last tag or within a specific date range.
2. **Filter & Group**: Discard noise (merge commits, minor style fixes) and group by type.
3. **Draft Content**: Write the changelog entries.
4. **Review**: Present the draft to the user for final edits before saving.

## Example Output
```markdown
## [1.2.0] - 2023-10-27

### 🚀 New Features
- Added Dark Mode support for the dashboard.
- Users can now export reports as PDF.

### 🐛 Bug Fixes
- Resolved a crash when uploading large images.
- Fixed navigation menu overlap on mobile devices.
```
