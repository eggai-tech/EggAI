# Code Quality Review

Review the code for:
- **Bugs & Logic Errors** — incorrect behavior, off-by-one errors, null/undefined issues
- **Security** — injection, auth issues, data exposure, insecure defaults
- **Performance** — unnecessary allocations, N+1 queries, missing indexes
- **Maintainability** — unclear naming, excessive complexity, missing error handling

For each issue found, provide:
1. The file path and line number
2. Severity (critical / high / medium / low)
3. A clear description of the problem
4. A suggested fix
