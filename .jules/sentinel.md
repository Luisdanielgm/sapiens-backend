## 2025-12-14 - Flask-Limiter Integration
**Vulnerability:** Lack of rate limiting on authentication endpoints exposed the API to brute-force attacks.
**Learning:** Initializing Flask-Limiter requires care with JSON responses. By default, it returns HTML 429 pages. Added a specific error handler for 429 to return JSON. Also, testing required mocking DB connections before app import due to global service instantiation.
**Prevention:** Always verify default error responses for new middleware libraries in API contexts.
