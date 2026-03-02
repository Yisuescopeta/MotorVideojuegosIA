---
name: postgresql
description: Best practices for PostgreSQL database design, querying, and optimization. Use this skill when designing schemas, writing complex SQL, or optimizing database performance.
license: MIT
---

# PostgreSQL Best Practices

## Schema Design

### 1. Data Integrity
- **Constraints**: Use `NOT NULL`, `UNIQUE`, `CHECK`, and `FOREIGN KEY` constraints. Let the database enforce data quality, not just the application.
- **Types**: Use appropriate types. 
    - Use `TIMESTAMPTZ` (timestamp with time zone) for events.
    - Use `TEXT` over `VARCHAR(n)` unless you have a hard limit (Postgres handles TEXT efficiently).
    - Use `UUID` for IDs if creating distributed systems or avoiding enumeration attacks.

### 2. Normalization
- **3NF**: Aim for 3rd Normal Form to reduce redundancy.
- **JSONB**: Use `JSONB` for unstructured data, but don't use it to avoid schema design. If you query inside the JSON often, extract it to a column.

## Querying

### 1. Safety
- **Parameterization**: ALWAYS use parameterized queries or prepared statements. NEVER concatenate strings into SQL.
    - Bad: `SELECT * FROM users WHERE id = ` + input
    - Good: `SELECT * FROM users WHERE id = $1`

### 2. Performance
- **Indexes**: Index columns used in `WHERE`, `JOIN`, and `ORDER BY` clauses.
    - Don't over-index (slows down writes).
    - Use `EXPLAIN ANALYZE` to check if indexes are being used.
- **Select Specific Columns**: `SELECT id, name` is better than `SELECT *`.
- **Joins**: Prefer excessive JOINs over N+1 query loops in application code.

### 3. Transactions
- **ACID**: Wrap multi-step operations in `BEGIN ... COMMIT`.
- **Row Locking**: Use `SELECT ... FOR UPDATE` carefully when reading data you intend to modify immediately, to prevent race conditions.

## Advanced Features
- **Views**: Use Views to abstract complex joins for read-only access.
- **Functions/Procedures**: Use PL/pgSQL for logic that requires heavy data manipulation close to the storage, but avoid putting business logic in the DB if possible (harder to test/version).
