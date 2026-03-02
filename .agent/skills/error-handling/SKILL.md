---
name: error-handling
description: Implement robust error handling patterns. Enforces best practices for catching, logging, and responding to errors in a way that preserves system stability and aids debugging.
license: MIT
---

# Error Handling Patterns

## Overview
Errors are inevitable. How you handle them defines the reliability of your software.

## Core Principles

### 1. Fail Fast, Fail Loudly (in Development)
- **Don't Swallow Errors**: Never use empty `catch` blocks.
- **Validate Early**: Check inputs at the boundary of your system (API endpoints, public methods).

### 2. Specific Exceptions
- **Catch Specific Types**: Don't just catch `Exception` or `Error`. Catch `FileNotFoundException`, `ValidationException`, etc.
- **Custom Exceptions**: Create domain-specific exceptions (e.g., `InsufficientFundsException`) to handle business logic failures distinctly from system crashes.

### 3. Contextual Logging
- **Log the "Why"**: Don't just log "Error happened." Log "Failed to process payment for user X because Y."
- **Include Stack Traces**: Always preserve the stack trace when re-throwing or logging (but define a boundary where they are sanitized for the user).

### 4. User-Facing vs. System Errors
- **Sanitize**: Never show raw stack traces or database errors to the end-user.
- **User Messages**: Show helpful messages ("Something went wrong, please try again") with a correlation ID for support.

### 5. Cleanup
- **Finally**: Use `finally` blocks (or language equivalents like `defer` or `using`) to ensure resources (files, connections) are closed even if an error occurs.

## Code Patterns

### The "Result" Pattern (Functional)
Instead of throwing exceptions for expected failures, return a Result type:
```typescript
type Result<T, E> = { ok: true, value: T } | { ok: false, error: E };
```

### The "Guard Clause" Pattern
Fail fast at the top of the function to avoid nesting.
```javascript
function process(data) {
  if (!data) throw new Error("Data required");
  if (!data.isValid) throw new Error("Invalid data");
  // ... actual logic
}
```

### Global Error Handler
Ensure every application (Web, CLI) has a top-level catch-all handler to log unhandled crashes and exit gracefully.
