---
name: interface-design
description: Design professional, polished, and consistent user interfaces. Use this skill when designing dashboards, admin panels, tools, or interactive products. Enforces a minimal, decent, and precise design system inspired by Linear, Notion, and Stripe.
license: MIT
---

# Interface Design Principles

## Overview
This skill guides the creation of professional interfaces with "Jony Ive-level precision." The goal is a clean, modern, and minimalist aesthetic where every pixel matters.

## Core Principles

### 1. Precision & Minimalism
- **Less is More**: Remove unnecessary elements. Every border, shadow, and color must have a purpose.
- **Micro-Details**: Obsess over small details. Padding, border-radius, and font-weight should be consistent and intentional.
- **Inspiration**: Draw from high-quality product designs like Linear, Notion, and Stripe.

### 2. Consistency (Systematic Design)
- **Design System**: Use a strict set of tokens for colors, spacing, and typography.
- **Preserve Decisions**: Don't invent new styles for every component. Reuse existing patterns.
- **Spacing Scale**: Use a consistent spacing scale (e.g., 4px grid: 4, 8, 12, 16, 24, 32, 48, 64px).

### 3. Visual Hierarchy
- **Contrast**: Use contrast to guide the eye, not just size. varying shades of gray (50-900) are powerful tools.
- **Typography**: Use a clear type scale. Headings should be distinct but not overpowering. Body text must be legible (high contrast against background).
- **Depth**: Use subtle shadows and borders to create depth. Avoid flat design if it hurts usability, but avoid skeuomorphism.

### 4. Interactive Feedback
- **States**: Every interactive element must have clear hover, active, focus, and disabled states.
- **Transitions**: Use fast, subtle transitions (e.g., 150ms-200ms ease-out) for all state changes. Instant changes feel cheap.

## Execution Guidelines
- **Tokens**: Define CSS variables for all colors and spacing at the start.
- **Components**: Build small, reusable components.
- **Feedback**: Ensure the interface feels "alive" and responsive to user input.

## Anti-Patterns
- **Inconsistent Spacing**: Don't mix 10px and 12px padding randomly. Stick to the grid.
- **Generic Bootstrap Look**: Avoid default browser styles or generic framework themes.
- **Visual Clutter**: If an element doesn't add value, remove it.
