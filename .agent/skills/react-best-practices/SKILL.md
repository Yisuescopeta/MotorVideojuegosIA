---
name: react-best-practices
description: Apply Vercel's expert performance optimization guidelines for React and Next.js. Use this skill when writing, reviewing, or refactoring React code to eliminate waterfalls, optimize bundle size, and improve rendering performance. Contains over 40 prioritized rules.
license: Unknown (Vercel Labs)
---

# Vercel React Best Practices

## When to Apply
Apply these rules when:
- Writing new React components or pages
- Reviewing code for performance
- Refactoring existing applications
- Optimizing Core Web Vitals (LCP, INP, CLS)

## Critical Rules (Must Fix)

### 1. Eliminating Waterfalls
Waterfalls (sequential data fetching) are the #1 killer of React performance.

*   **Move `await` to usage (`async-defer-await`)**: Do not `await` promises immediately if their results aren't needed yet. Start the promise, do other work, then await.
*   **Use `Promise.all` (`async-parallel`)**: If two requests are independent, fetch them in parallel.
    ```javascript
    // BAD
    const user = await getUser();
    const posts = await getPosts();

    // GOOD
    const [user, posts] = await Promise.all([getUser(), getPosts()]);
    ```
*   **Start promises early (`async-api-routes`)**: In API routes, start DB queries or fetches as early as possible, before doing other processing.
*   **Use Suspense (`async-suspense-boundaries`)**: Wrap slow components in `<Suspense>` so they don't block the entire page from streaming.

### 2. Bundle Size Optimization
*   **Avoid Barrel Files (`bundle-barrel-imports`)**: Do NOT import from `index.ts` barrel files if they re-export large libraries. Import directly from the specific file.
    ```javascript
    // BAD
    import { Button, Modal, HeavyChart } from './components'; // Loads everything

    // GOOD
    import { Button } from './components/Button';
    import { Modal } from './components/Modal';
    ```
*   **Use Dynamic Imports (`bundle-dynamic-imports`)**: Lazily load heavy components (charts, maps, editors) that aren't visible immediately using `next/dynamic` or `React.lazy`.

## High Priority Rules

### 3. Server-Side Performance
*   **Server Actions as APIs (`server-auth-actions`)**: Treat Server Actions like public API endpoints. Always validate authentication and authorization inside the action.
*   **Deduplicate Requests**: Use `React.cache` for per-request memoization of database calls or expensive computations on the server.

### 4. Client-Side Data Fetching
*   **Deduplicate Client Requests (`client-swr-dedup`)**: Use libraries like SWR or TanStack Query to automatically deduplicate requests and cache responses. Avoid raw `useEffect` for data fetching if possible.

## Medium Priority Rules

### 5. Re-render Optimization
*   **Defer State Reads (`rerender-defer-reads`)**: Don't read state in a parent component just to pass it to a child if the parent doesn't use it. Pass the state setter or use composition.
*   **Memoize Expensive Computations**: Use `useMemo` for heavy calculations that run on every render.
*   **Stable Callbacks**: Use `useCallback` for functions passed as props to memoized components.

### 6. Rendering Performance
*   **Optimize Images**: Always use `next/image` for automatic sizing and format optimization.
*   **Font Optimization**: Use `next/font` to eliminate layout shift and reduce fetch time.

## Low Priority Rules

### 7. JavaScript Performance
*   **Avoid Large Libraries**: Prefer lightweight alternatives (e.g., specific `date-fns` imports vs `moment.js`).

## Advanced Patterns
*   **Streaming**: Use React Server Components and Streaming to send HTML chunks as they generate, improving TTFB.

---
**Summary**: Prioritize fixing waterfalls and bundle size issues first. These have the largest impact on user experience.
