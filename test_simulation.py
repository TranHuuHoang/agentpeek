#!/usr/bin/env python3
"""Simulate realistic multi-agent sessions for testing AgentPeek UI."""
import json
import time
import uuid
import random

JSONL_PATH = "/tmp/agentpeek.jsonl"

def uid():
    return f"toolu_{uuid.uuid4().hex[:24]}"

def agent_uid():
    return f"agent-{uuid.uuid4().hex[:8]}"

def write_event(event):
    with open(JSONL_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")
    time.sleep(0.05)  # small delay so events have distinct timestamps

def pre_tool(session_id, agent_id, agent_type, tool_name, tool_input, tool_use_id=None):
    tuid = tool_use_id or uid()
    write_event({
        "hook": "PreToolUse",
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": agent_type,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_use_id": tuid,
        "cwd": "/Users/dev/projects/webapp" if "sess1" in session_id else "/Users/dev/projects/api-service" if "sess2" in session_id else "/Users/dev/projects/stuck-demo",
    })
    return tuid

def post_tool(session_id, agent_id, agent_type, tool_name, tool_response, tool_use_id, is_error=False):
    write_event({
        "hook": "PostToolUseFailure" if is_error else "PostToolUse",
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": agent_type,
        "tool_name": tool_name,
        "tool_response": tool_response,
        "tool_use_id": tool_use_id,
        "cwd": "/Users/dev/projects/webapp" if "sess1" in session_id else "/Users/dev/projects/api-service" if "sess2" in session_id else "/Users/dev/projects/stuck-demo",
    })

def spawn_agent(session_id, parent_id, parent_type, description, subagent_type, prompt):
    """Simulate PreToolUse(Agent) -> SubagentStart -> agent does work -> SubagentStop"""
    tool_use_id = uid()
    agent_id = agent_uid()

    # Parent calls Agent tool
    pre_tool(session_id, parent_id, parent_type, "Agent", {
        "description": description,
        "prompt": prompt,
        "subagent_type": subagent_type,
    }, tool_use_id)
    time.sleep(0.1)

    # SubagentStart fires
    write_event({
        "hook": "SubagentStart",
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": subagent_type or "general-purpose",
        "tool_use_id": tool_use_id,
        "tool_input": {
            "description": description,
            "prompt": prompt,
            "subagent_type": subagent_type,
        },
        "cwd": "/Users/dev/projects/webapp" if "sess1" in session_id else "/Users/dev/projects/api-service" if "sess2" in session_id else "/Users/dev/projects/stuck-demo",
    })
    time.sleep(0.1)

    return agent_id, tool_use_id, subagent_type

def stop_agent(session_id, agent_id, agent_type, result, tool_use_id=None):
    write_event({
        "hook": "SubagentStop",
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": agent_type,
        "tool_use_id": tool_use_id or "",
        "result": result,
        "cwd": "/Users/dev/projects/webapp" if "sess1" in session_id else "/Users/dev/projects/api-service" if "sess2" in session_id else "/Users/dev/projects/stuck-demo",
    })

def end_session(session_id):
    write_event({
        "hook": "Stop",
        "session_id": session_id,
        "cwd": "/Users/dev/projects/webapp" if "sess1" in session_id else "/Users/dev/projects/api-service" if "sess2" in session_id else "/Users/dev/projects/stuck-demo",
    })


# ─── SESSION 1: Web App Feature Implementation ───────────────────────────
print("=== Session 1: Web App Feature Implementation ===")
S1 = "sess1-" + uuid.uuid4().hex[:8]
ROOT1 = f"root:{S1}"

# Root agent starts reading files
t1 = pre_tool(S1, "", "", "Read", {"file_path": "/Users/dev/projects/webapp/src/App.tsx"})
time.sleep(0.3)
post_tool(S1, "", "", "Read", "import React from 'react'\nexport default function App() { return <div>Hello</div> }", t1)

t2 = pre_tool(S1, "", "", "Glob", {"pattern": "src/**/*.tsx"})
time.sleep(0.2)
post_tool(S1, "", "", "Glob", "src/App.tsx\nsrc/components/Header.tsx\nsrc/components/Sidebar.tsx\nsrc/pages/Dashboard.tsx", t2)

# Spawn 3 parallel agents
print("  Spawning parallel agents...")

# Agent 1: Explore codebase
explore_id, explore_tuid, explore_type = spawn_agent(
    S1, "", "", "Explore component structure",
    "Explore", "Search the codebase for all React components. Map out the component hierarchy and identify shared state patterns."
)

# Agent 2: Plan implementation
plan_id, plan_tuid, plan_type = spawn_agent(
    S1, "", "", "Plan authentication flow",
    "Plan", "Design the implementation plan for adding OAuth2 authentication. Consider existing middleware, session management, and route protection."
)

# Agent 3: Research best practices
research_id, research_tuid, research_type = spawn_agent(
    S1, "", "", "Research OAuth patterns",
    "Explore", "Research OAuth2 best practices for React SPAs. Look at how popular libraries handle token refresh, PKCE flow, and secure storage."
)

# Explore agent does work
time.sleep(0.2)
for i, file in enumerate(["Header.tsx", "Sidebar.tsx", "Dashboard.tsx", "UserProfile.tsx", "AuthContext.tsx"]):
    t = pre_tool(S1, explore_id, "Explore", "Read", {"file_path": f"/Users/dev/projects/webapp/src/components/{file}"})
    time.sleep(0.15)
    post_tool(S1, explore_id, "Explore", "Read", f"// {file} component content\nexport function {file.replace('.tsx','')}() {{ return <div>{file}</div> }}", t)

t = pre_tool(S1, explore_id, "Explore", "Grep", {"pattern": "useContext|createContext|Provider", "glob": "*.tsx"})
time.sleep(0.2)
post_tool(S1, explore_id, "Explore", "Grep", "src/AuthContext.tsx:5: const AuthContext = createContext(null)\nsrc/App.tsx:12: <AuthProvider>", t)

# Explore done
time.sleep(0.1)
stop_agent(S1, explore_id, "Explore", "Found 12 components. AuthContext exists but is minimal. No route protection. State managed via Context + useState.", explore_tuid)

# Plan agent does work
time.sleep(0.1)
t = pre_tool(S1, plan_id, "Plan", "Read", {"file_path": "/Users/dev/projects/webapp/src/middleware/auth.ts"})
time.sleep(0.3)
post_tool(S1, plan_id, "Plan", "Read", "export function requireAuth(req, res, next) { /* basic auth check */ }", t)

t = pre_tool(S1, plan_id, "Plan", "Read", {"file_path": "/Users/dev/projects/webapp/package.json"})
time.sleep(0.2)
post_tool(S1, plan_id, "Plan", "Read", '{"dependencies": {"react": "^18.2.0", "react-router-dom": "^6.8.0"}}', t)

# Plan spawns a sub-agent for detailed design
detail_id, detail_tuid, detail_type = spawn_agent(
    S1, plan_id, "Plan", "Design token storage strategy",
    "general-purpose", "Analyze the best approach for storing OAuth tokens in this React app. Consider: localStorage vs memory vs httpOnly cookies. Evaluate XSS and CSRF risks."
)

time.sleep(0.2)
t = pre_tool(S1, detail_id, "general-purpose", "WebSearch", {"query": "OAuth2 token storage React SPA security best practices 2024"})
time.sleep(0.5)
post_tool(S1, detail_id, "general-purpose", "WebSearch", "Results: 1. Use httpOnly cookies for refresh tokens, 2. In-memory for access tokens, 3. Never localStorage for sensitive tokens", t)

t = pre_tool(S1, detail_id, "general-purpose", "Read", {"file_path": "/Users/dev/projects/webapp/src/config/security.ts"})
time.sleep(0.2)
post_tool(S1, detail_id, "general-purpose", "Read", "Error: File not found", t, is_error=True)

# Retry after error
t = pre_tool(S1, detail_id, "general-purpose", "Glob", {"pattern": "src/**/security*"})
time.sleep(0.15)
post_tool(S1, detail_id, "general-purpose", "Glob", "No matches found", t)

t = pre_tool(S1, detail_id, "general-purpose", "Write", {"file_path": "/Users/dev/projects/webapp/src/config/security.ts", "content": "export const TOKEN_CONFIG = { storage: 'memory', refreshCookie: true }"})
time.sleep(0.2)
post_tool(S1, detail_id, "general-purpose", "Write", "File written successfully", t)

stop_agent(S1, detail_id, "general-purpose", "Recommended: in-memory access tokens + httpOnly cookie refresh tokens. Created security.ts config.", detail_tuid)

# Plan done
time.sleep(0.2)
stop_agent(S1, plan_id, "Plan", "Implementation plan:\n1. Add @auth0/auth0-react\n2. Create AuthProvider wrapper\n3. Add ProtectedRoute component\n4. Update App.tsx routing\n5. Add login/logout pages\n6. Token refresh middleware", plan_tuid)

# Research agent does work (in parallel with plan)
time.sleep(0.1)
t = pre_tool(S1, research_id, "Explore", "WebSearch", {"query": "React OAuth2 PKCE flow implementation"})
time.sleep(0.4)
post_tool(S1, research_id, "Explore", "WebSearch", "auth0-react, react-oidc-context, nextauth — all support PKCE", t)

t = pre_tool(S1, research_id, "Explore", "WebFetch", {"url": "https://auth0.com/docs/quickstart/spa/react"})
time.sleep(0.3)
post_tool(S1, research_id, "Explore", "WebFetch", "Auth0 React quickstart: npm install @auth0/auth0-react, wrap App in Auth0Provider...", t)

t = pre_tool(S1, research_id, "Explore", "WebFetch", {"url": "https://react-oidc-context.js.org/docs/getting-started"})
time.sleep(0.2)
post_tool(S1, research_id, "Explore", "WebFetch", "Error: Connection timeout", t, is_error=True)

# Retry
t = pre_tool(S1, research_id, "Explore", "WebSearch", {"query": "react-oidc-context vs auth0-react comparison"})
time.sleep(0.3)
post_tool(S1, research_id, "Explore", "WebSearch", "auth0-react is more popular (2.3k stars), better docs, built-in token refresh", t)

stop_agent(S1, research_id, "Explore", "Recommendation: Use @auth0/auth0-react for PKCE flow. Well-maintained, 2.3k stars, built-in token refresh. Alternative: react-oidc-context for non-Auth0 providers.", research_tuid)

# Root spawns implementation agents based on plan results
print("  Spawning implementation agents...")
time.sleep(0.3)

# Agent 4: Write auth components
write_auth_id, write_auth_tuid, write_auth_type = spawn_agent(
    S1, "", "", "Implement auth components",
    "general-purpose", "Implement the OAuth2 authentication components:\n1. AuthProvider wrapper\n2. ProtectedRoute component\n3. LoginPage\n4. LogoutButton\nUse @auth0/auth0-react."
)

# Agent 5: Write tests
write_tests_id, write_tests_tuid, write_tests_type = spawn_agent(
    S1, "", "", "Write authentication tests",
    "general-purpose", "Write comprehensive tests for the auth components: AuthProvider, ProtectedRoute, LoginPage. Mock Auth0 hooks. Test redirect flows."
)

# Write auth components
time.sleep(0.2)
for file, content in [
    ("AuthProvider.tsx", "export function AuthProvider({ children }) { return <Auth0Provider>{children}</Auth0Provider> }"),
    ("ProtectedRoute.tsx", "export function ProtectedRoute({ children }) { const { isAuthenticated } = useAuth0(); return isAuthenticated ? children : <Navigate to='/login' /> }"),
    ("LoginPage.tsx", "export function LoginPage() { const { loginWithRedirect } = useAuth0(); return <button onClick={loginWithRedirect}>Login</button> }"),
    ("LogoutButton.tsx", "export function LogoutButton() { const { logout } = useAuth0(); return <button onClick={logout}>Logout</button> }"),
]:
    t = pre_tool(S1, write_auth_id, "general-purpose", "Write", {"file_path": f"/Users/dev/projects/webapp/src/components/auth/{file}", "content": content})
    time.sleep(0.2)
    post_tool(S1, write_auth_id, "general-purpose", "Write", "File written", t)

t = pre_tool(S1, write_auth_id, "general-purpose", "Edit", {"file_path": "/Users/dev/projects/webapp/src/App.tsx", "old_string": "<div>Hello</div>", "new_string": "<AuthProvider><Router><ProtectedRoute>...</ProtectedRoute></Router></AuthProvider>"})
time.sleep(0.15)
post_tool(S1, write_auth_id, "general-purpose", "Edit", "Edit applied", t)

stop_agent(S1, write_auth_id, "general-purpose", "Created 4 auth components: AuthProvider, ProtectedRoute, LoginPage, LogoutButton. Updated App.tsx with auth wrapper and protected routing.", write_auth_tuid)

# Write tests (with some failures)
time.sleep(0.2)
t = pre_tool(S1, write_tests_id, "general-purpose", "Write", {"file_path": "/Users/dev/projects/webapp/src/__tests__/auth.test.tsx", "content": "describe('Auth', () => { ... })"})
time.sleep(0.3)
post_tool(S1, write_tests_id, "general-purpose", "Write", "File written", t)

t = pre_tool(S1, write_tests_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/webapp && npm test -- --run auth.test"})
time.sleep(0.5)
post_tool(S1, write_tests_id, "general-purpose", "Bash", "FAIL: AuthProvider test failed - useAuth0 not mocked correctly\n2 passed, 1 failed", t, is_error=True)

# Fix and retry
t = pre_tool(S1, write_tests_id, "general-purpose", "Edit", {"file_path": "/Users/dev/projects/webapp/src/__tests__/auth.test.tsx", "old_string": "mock useAuth0", "new_string": "jest.mock('@auth0/auth0-react', () => ({useAuth0: () => ({isAuthenticated: true})}))"})
time.sleep(0.2)
post_tool(S1, write_tests_id, "general-purpose", "Edit", "Edit applied", t)

t = pre_tool(S1, write_tests_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/webapp && npm test -- --run auth.test"})
time.sleep(0.4)
post_tool(S1, write_tests_id, "general-purpose", "Bash", "PASS: 3 tests passed\n  ✓ AuthProvider renders children\n  ✓ ProtectedRoute redirects unauthenticated\n  ✓ LoginPage calls loginWithRedirect", t)

stop_agent(S1, write_tests_id, "general-purpose", "All 3 auth tests passing. Fixed mock setup for useAuth0.", write_tests_tuid)

# Root does final work
time.sleep(0.2)
t = pre_tool(S1, "", "", "Bash", {"command": "cd /Users/dev/projects/webapp && npm run build"})
time.sleep(0.5)
post_tool(S1, "", "", "Bash", "Build successful. No warnings.", t)

# End session
time.sleep(0.3)
end_session(S1)
print(f"  Session 1 complete: {S1}")


# ─── SESSION 2: API Service Debugging ────────────────────────────────────
print("\n=== Session 2: API Service Debugging ===")
S2 = "sess2-" + uuid.uuid4().hex[:8]

time.sleep(0.5)

# Root reads error logs
t = pre_tool(S2, "", "", "Bash", {"command": "tail -50 /var/log/api-service/error.log"})
time.sleep(0.3)
post_tool(S2, "", "", "Bash", "2024-03-24 ERROR: Connection pool exhausted\n2024-03-24 ERROR: Query timeout after 30s on /api/users\n2024-03-24 WARN: Slow query detected: SELECT * FROM orders JOIN users", t)

t = pre_tool(S2, "", "", "Read", {"file_path": "/Users/dev/projects/api-service/src/routes/users.py"})
time.sleep(0.2)
post_tool(S2, "", "", "Read", "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/users')\nasync def list_users(db = Depends(get_db)): return await db.execute('SELECT * FROM users')", t)

# Spawn investigation agents
print("  Spawning investigation agents...")

# Agent 1: Database analysis
db_id, db_tuid, db_type = spawn_agent(
    S2, "", "", "Analyze database performance",
    "Explore", "Investigate the database performance issues. Check connection pool config, slow queries, missing indexes. Look at the ORM queries and suggest optimizations."
)

# Agent 2: API profiling
api_id, api_tuid, api_type = spawn_agent(
    S2, "", "", "Profile API endpoints",
    "Explore", "Profile the slow API endpoints. Check /api/users and /api/orders for N+1 queries, missing pagination, and inefficient joins."
)

# DB analysis agent
time.sleep(0.2)
t = pre_tool(S2, db_id, "Explore", "Read", {"file_path": "/Users/dev/projects/api-service/src/db/config.py"})
time.sleep(0.2)
post_tool(S2, db_id, "Explore", "Read", "POOL_SIZE = 5\nMAX_OVERFLOW = 0\nPOOL_TIMEOUT = 30", t)

t = pre_tool(S2, db_id, "Explore", "Grep", {"pattern": "create_engine|pool_size", "glob": "*.py"})
time.sleep(0.15)
post_tool(S2, db_id, "Explore", "Grep", "src/db/config.py:3: engine = create_engine(URL, pool_size=5, max_overflow=0)", t)

t = pre_tool(S2, db_id, "Explore", "Bash", {"command": "psql -c 'SELECT * FROM pg_stat_activity WHERE state = \\'active\\'' | head -20"})
time.sleep(0.3)
post_tool(S2, db_id, "Explore", "Bash", "5 active connections, all executing SELECT * FROM orders JOIN users...", t)

t = pre_tool(S2, db_id, "Explore", "Bash", {"command": "psql -c 'EXPLAIN ANALYZE SELECT * FROM orders JOIN users ON orders.user_id = users.id'"})
time.sleep(0.2)
post_tool(S2, db_id, "Explore", "Bash", "Seq Scan on orders (cost=0.00..12345.00 rows=100000)\n  -> Seq Scan on users (cost=0.00..5000.00 rows=50000)\nExecution time: 2340.123 ms", t)

stop_agent(S2, db_id, "Explore", "Root cause: Pool size too small (5), no index on orders.user_id causing sequential scan on 100k rows. Missing: orders_user_id_idx, pagination on /api/users.", db_tuid)

# API profiling agent
time.sleep(0.1)
t = pre_tool(S2, api_id, "Explore", "Read", {"file_path": "/Users/dev/projects/api-service/src/routes/orders.py"})
time.sleep(0.2)
post_tool(S2, api_id, "Explore", "Read", "@router.get('/orders')\nasync def list_orders(db=Depends(get_db)):\n    orders = await db.execute('SELECT * FROM orders')\n    for o in orders:\n        o.user = await db.execute('SELECT * FROM users WHERE id = ?', o.user_id)  # N+1!", t)

t = pre_tool(S2, api_id, "Explore", "Grep", {"pattern": "SELECT.*FROM.*WHERE", "glob": "*.py"})
time.sleep(0.2)
post_tool(S2, api_id, "Explore", "Grep", "routes/orders.py:5: N+1 query detected\nroutes/products.py:12: Similar pattern", t)

t = pre_tool(S2, api_id, "Explore", "Read", {"file_path": "/Users/dev/projects/api-service/src/routes/products.py"})
time.sleep(0.15)
post_tool(S2, api_id, "Explore", "Read", "# Products route with eager loading - OK", t)

stop_agent(S2, api_id, "Explore", "Found N+1 query in /api/orders (fetches user per order). /api/products is OK. Recommend: JOIN query or eager loading for orders.", api_tuid)

# Root spawns fix agents
print("  Spawning fix agents...")
time.sleep(0.2)

fix_db_id, fix_db_tuid, fix_db_type = spawn_agent(
    S2, "", "", "Fix database configuration",
    "general-purpose", "Fix the database issues:\n1. Increase pool_size from 5 to 20\n2. Add max_overflow=10\n3. Create index on orders.user_id\n4. Add connection health checks"
)

fix_api_id, fix_api_tuid, fix_api_type = spawn_agent(
    S2, "", "", "Fix N+1 queries in orders",
    "general-purpose", "Fix the N+1 query in /api/orders:\n1. Replace loop query with JOIN\n2. Add pagination (limit/offset)\n3. Add response caching"
)

fix_test_id, fix_test_tuid, fix_test_type = spawn_agent(
    S2, "", "", "Write performance tests",
    "general-purpose", "Write performance regression tests for the fixed endpoints. Verify query count, response time, and connection pool behavior."
)

# Fix DB config
time.sleep(0.2)
t = pre_tool(S2, fix_db_id, "general-purpose", "Edit", {"file_path": "/Users/dev/projects/api-service/src/db/config.py", "old_string": "POOL_SIZE = 5", "new_string": "POOL_SIZE = 20"})
time.sleep(0.15)
post_tool(S2, fix_db_id, "general-purpose", "Edit", "Edit applied", t)

t = pre_tool(S2, fix_db_id, "general-purpose", "Bash", {"command": "psql -c 'CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders(user_id)'"})
time.sleep(0.4)
post_tool(S2, fix_db_id, "general-purpose", "Bash", "CREATE INDEX", t)

t = pre_tool(S2, fix_db_id, "general-purpose", "Edit", {"file_path": "/Users/dev/projects/api-service/src/db/config.py", "old_string": "MAX_OVERFLOW = 0", "new_string": "MAX_OVERFLOW = 10\nPOOL_PRE_PING = True"})
time.sleep(0.15)
post_tool(S2, fix_db_id, "general-purpose", "Edit", "Edit applied", t)

stop_agent(S2, fix_db_id, "general-purpose", "Fixed: pool_size 5→20, max_overflow 0→10, added pool_pre_ping. Created idx_orders_user_id index.", fix_db_tuid)

# Fix N+1 query
time.sleep(0.1)
t = pre_tool(S2, fix_api_id, "general-purpose", "Edit", {"file_path": "/Users/dev/projects/api-service/src/routes/orders.py", "old_string": "for o in orders", "new_string": "# Use JOIN query\norders = await db.execute('SELECT o.*, u.name FROM orders o JOIN users u ON o.user_id = u.id LIMIT 100')"})
time.sleep(0.2)
post_tool(S2, fix_api_id, "general-purpose", "Edit", "Edit applied", t)

t = pre_tool(S2, fix_api_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/api-service && python -m pytest tests/test_orders.py -v"})
time.sleep(0.3)
post_tool(S2, fix_api_id, "general-purpose", "Bash", "FAILED: test_list_orders - AssertionError: expected 'user' key in response", t, is_error=True)

# Fix test
t = pre_tool(S2, fix_api_id, "general-purpose", "Edit", {"file_path": "/Users/dev/projects/api-service/src/routes/orders.py", "old_string": "u.name", "new_string": "u.name as user_name, u.email as user_email"})
time.sleep(0.15)
post_tool(S2, fix_api_id, "general-purpose", "Edit", "Edit applied", t)

t = pre_tool(S2, fix_api_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/api-service && python -m pytest tests/test_orders.py -v"})
time.sleep(0.3)
post_tool(S2, fix_api_id, "general-purpose", "Bash", "PASSED: 4 tests passed in 0.3s", t)

stop_agent(S2, fix_api_id, "general-purpose", "Fixed N+1 query: replaced loop with JOIN. Added pagination (LIMIT 100). All tests passing.", fix_api_tuid)

# Performance tests
time.sleep(0.1)
t = pre_tool(S2, fix_test_id, "general-purpose", "Write", {"file_path": "/Users/dev/projects/api-service/tests/test_performance.py", "content": "import pytest\n@pytest.mark.slow\ndef test_orders_response_time(): ..."})
time.sleep(0.2)
post_tool(S2, fix_test_id, "general-purpose", "Write", "File written", t)

t = pre_tool(S2, fix_test_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/api-service && python -m pytest tests/test_performance.py -v --timeout=5"})
time.sleep(0.4)
post_tool(S2, fix_test_id, "general-purpose", "Bash", "PASSED: test_orders_response_time (0.12s)\nPASSED: test_users_response_time (0.08s)\nPASSED: test_connection_pool_under_load (1.2s)", t)

stop_agent(S2, fix_test_id, "general-purpose", "All 3 performance tests passing. Orders endpoint: 0.12s (was 2.3s). Connection pool handles 50 concurrent requests.", fix_test_tuid)

# End session 2
time.sleep(0.2)
t = pre_tool(S2, "", "", "Bash", {"command": "cd /Users/dev/projects/api-service && git diff --stat"})
time.sleep(0.2)
post_tool(S2, "", "", "Bash", "src/db/config.py | 4 ++--\nsrc/routes/orders.py | 8 +++-----\ntests/test_performance.py | 25 ++++++++++++++++\n3 files changed, 30 insertions(+), 7 deletions(-)", t)

end_session(S2)
print(f"  Session 2 complete: {S2}")

# ─── SESSION 3: Stuck Agent Demo ────────────────────────────────────
print("\n=== Session 3: Stuck Agent Demo ===")
S3 = "sess3-" + uuid.uuid4().hex[:8]

# Root reads a file
t = pre_tool(S3, "", "", "Read", {"file_path": "/Users/dev/projects/stuck-demo/src/main.py"})
time.sleep(0.2)
post_tool(S3, "", "", "Read", "def main(): pass", t)

# Spawn an agent that gets stuck reading a non-existent file
stuck_read_id, stuck_read_tuid, stuck_read_type = spawn_agent(
    S3, "", "", "Find configuration file",
    "Explore", "Find and read the configuration file for the deployment pipeline."
)

# Agent tries to read the same non-existent file 4 times (Pattern A: repeated_tool)
time.sleep(0.2)
for i in range(4):
    t = pre_tool(S3, stuck_read_id, "Explore", "Read", {"file_path": "/Users/dev/projects/stuck-demo/config/deploy.yaml"})
    time.sleep(0.15)
    post_tool(S3, stuck_read_id, "Explore", "Read", "Error: File not found: deploy.yaml", t, is_error=True)

# Don't stop this agent — it's stuck

# Spawn another agent that has consecutive bash failures (Pattern B: failure_loop)
stuck_bash_id, stuck_bash_tuid, stuck_bash_type = spawn_agent(
    S3, "", "", "Run deployment script",
    "general-purpose", "Execute the deployment script to deploy the latest changes to staging."
)

time.sleep(0.2)
for i in range(3):
    t = pre_tool(S3, stuck_bash_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/stuck-demo && ./deploy.sh --env staging"})
    time.sleep(0.2)
    post_tool(S3, stuck_bash_id, "general-purpose", "Bash", f"Error: Connection refused to staging-server.internal:8080 (attempt {i+1})", t, is_error=True)

# Don't stop this agent either — it's stuck

# Spawn a healthy agent that completes normally for contrast
healthy_id, healthy_tuid, healthy_type = spawn_agent(
    S3, "", "", "Check service health",
    "Explore", "Check the health status of all microservices."
)

time.sleep(0.2)
t = pre_tool(S3, healthy_id, "Explore", "Bash", {"command": "curl -s http://localhost:8080/health"})
time.sleep(0.2)
post_tool(S3, healthy_id, "Explore", "Bash", '{"status": "healthy", "services": ["api", "db", "cache"]}', t)

t = pre_tool(S3, healthy_id, "Explore", "Bash", {"command": "curl -s http://localhost:8081/health"})
time.sleep(0.15)
post_tool(S3, healthy_id, "Explore", "Bash", '{"status": "healthy", "services": ["worker", "scheduler"]}', t)

stop_agent(S3, healthy_id, "Explore", "All 5 microservices are healthy: api, db, cache, worker, scheduler.", healthy_tuid)

# End session (stuck agents remain active)
time.sleep(0.3)
end_session(S3)
print(f"  Session 3 complete: {S3}")

print("\nDone! All 3 sessions simulated.")
