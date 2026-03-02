---
name: api-design
description: Design robust, scalable, and intuitive APIs (REST, GraphQL, etc.). Enforces best practices for resource naming, HTTP methods, error handling, versioning, and security. Use this when designing or refactoring backend endpoints.
license: MIT
---

# API Design Principles

## Overview
Great APIs are consistent, predictable, and easy to use. This skill enforces industry standards for API design.

## Core Principles

### 1. Resource-Oriented Design (REST)
- **Nouns, not Verbs**: Use resources (nouns) in methods.
    - Good: `GET /users`, `POST /users`
    - Bad: `GET /getUsers`, `POST /createUser`
- **Plural Nouns**: Use plural nouns for collections (`/users` not `/user`).
- **Nesting**: Use nesting to show relationships, but limit depth to 2-3 levels.
    - `GET /users/{id}/posts` (Okay)
    - `GET /users/{id}/posts/{pid}/comments` (Borderline)

### 2. HTTP Methods
- **GET**: Retrieve data. Safe and idempotent.
- **POST**: Create new resources. Not idempotent.
- **PUT**: Update/Replace a resource completely. Idempotent.
- **PATCH**: Partial update. Idempotent.
- **DELETE**: Remove a resource. Idempotent.

### 3. Responses & Status Codes
- **200 OK**: Success (GET, PUT, PATCH).
- **201 Created**: Success (POST) - Return the created resource.
- **204 No Content**: Success (DELETE) - No body returned.
- **400 Bad Request**: Client error (validation).
- **401 Unauthorized**: Missing/invalid authentication.
- **403 Forbidden**: Authenticated but not allowed.
- **404 Not Found**: Resource does not exist.
- **500 Internal Server Error**: Server bug.

### 4. Naming Conventions
- **Case**: Use `camelCase` for JSON fields and params (e.g., `firstName`). Use `kebab-case` for URLs (e.g., `/user-profiles`).
- **Consistency**: If you use `userId` in one place, don't use `user_id` or `id` elsewhere for the same concept.

### 5. Filtering, Sorting, Pagination
- **Pagination**: Always paginate collections. Use `limit` and `offset` or cursor-based pagination.
- **Filtering**: Use query parameters: `GET /users?role=admin`.
- **Sorting**: Use `sort` or `order`: `GET /users?sort=-createdAt` (descending).

### 6. GraphQL Specifics
- **Schema First**: Design the schema before implementation.
- **N+1 Problem**: Ensure resolvers use DataLoaders to batch database requests.
- **Naming**: Use verb-noun for mutations (`createUser`, `updatePost`).

## Security
- **HTTPS**: Always use HTTPS.
- **Authentication**: Use Bearer Tokens (JWT) in headers.
- **Rate Limiting**: Protect endpoints from abuse.
