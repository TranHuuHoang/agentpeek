#!/usr/bin/env python3
"""Demo simulation: impressive multi-layer agent team for video recording.

Scenario: "Build a full-stack SaaS authentication system"
- Root orchestrates 3 parallel research/plan agents
- Plan agent spawns 2 implementation sub-agents
- One implementation agent spawns a test writer (3 layers deep)
- Includes errors, retries, file operations, web searches
- Realistic timing with dramatic pauses for video
"""
import json
import time
import uuid

JSONL_PATH = "/tmp/agentpeek.jsonl"

def uid():
    return f"toolu_{uuid.uuid4().hex[:24]}"

def agent_uid():
    return f"agent-{uuid.uuid4().hex[:8]}"

def write_event(event):
    with open(JSONL_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")
    time.sleep(0.03)

def get_cwd():
    return "/Users/dev/projects/saas-platform"

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
        "cwd": get_cwd(),
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
        "cwd": get_cwd(),
    })

def spawn_agent(session_id, parent_id, parent_type, description, subagent_type, prompt):
    tool_use_id = uid()
    agent_id = agent_uid()
    pre_tool(session_id, parent_id, parent_type, "Agent", {
        "description": description,
        "prompt": prompt,
        "subagent_type": subagent_type,
    }, tool_use_id)
    time.sleep(0.08)
    write_event({
        "hook": "SubagentStart",
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": subagent_type or "general-purpose",
        "tool_use_id": tool_use_id,
        "tool_input": {"description": description, "prompt": prompt, "subagent_type": subagent_type},
        "cwd": get_cwd(),
    })
    time.sleep(0.08)
    return agent_id, tool_use_id, subagent_type

def stop_agent(session_id, agent_id, agent_type, result, tool_use_id=None):
    write_event({
        "hook": "SubagentStop",
        "session_id": session_id,
        "agent_id": agent_id,
        "agent_type": agent_type,
        "tool_use_id": tool_use_id or "",
        "result": result,
        "cwd": get_cwd(),
    })

def end_session(session_id):
    write_event({"hook": "Stop", "session_id": session_id, "cwd": get_cwd()})

def do_tool(sid, aid, atype, tool, inp, resp, delay=0.3, error=False):
    """Helper: PreToolUse + delay + PostToolUse"""
    t = pre_tool(sid, aid, atype, tool, inp)
    time.sleep(delay)
    post_tool(sid, aid, atype, tool, resp, t, is_error=error)
    return t


# ═══════════════════════════════════════════════════════════════════════
S = "demo-" + uuid.uuid4().hex[:8]
print("═" * 60)
print(f"  Demo: Build Full-Stack SaaS Auth System")
print(f"  Session: {S}")
print("═" * 60)

# ── Root agent reads codebase ─────────────────────────────────────────
print("\n▸ Root agent analyzing codebase...")
do_tool(S, "", "", "Read", {"file_path": "/Users/dev/projects/saas-platform/package.json"},
    '{"name": "saas-platform", "dependencies": {"next": "^14.2.0", "prisma": "^5.10.0", "next-auth": "^4.24.0"}}', 0.4)
do_tool(S, "", "", "Glob", {"pattern": "src/**/*.ts"},
    "src/app/page.tsx\nsrc/app/api/auth/[...nextauth]/route.ts\nsrc/lib/prisma.ts\nsrc/middleware.ts\nsrc/components/LoginForm.tsx\nsrc/components/SignupForm.tsx", 0.3)
do_tool(S, "", "", "Read", {"file_path": "/Users/dev/projects/saas-platform/prisma/schema.prisma"},
    'model User {\n  id       String @id @default(cuid())\n  email    String @unique\n  name     String?\n  accounts Account[]\n  sessions Session[]\n}', 0.3)

# ── Layer 1: Spawn 3 parallel research/planning agents ────────────────
print("\n▸ Spawning 3 parallel agents: research, security audit, plan...")
time.sleep(0.5)

research_id, research_tuid, _ = spawn_agent(S, "", "",
    "Research auth best practices",
    "Explore",
    "Research modern authentication patterns for Next.js SaaS apps. Compare NextAuth vs Clerk vs Auth0 vs Lucia. Evaluate: OAuth providers, magic links, passkeys, MFA support, pricing, and self-hosted options.")

security_id, security_tuid, _ = spawn_agent(S, "", "",
    "Security audit existing auth",
    "Explore",
    "Audit the existing authentication setup in this Next.js codebase. Check for: CSRF protection, session management, password hashing, rate limiting, JWT configuration, cookie security, and OWASP top 10 compliance.")

plan_id, plan_tuid, _ = spawn_agent(S, "", "",
    "Plan auth system architecture",
    "Plan",
    "Design the architecture for a production-grade authentication system. Requirements: multi-tenant, OAuth (Google/GitHub), magic links, role-based access control (RBAC), session management, and API key authentication for programmatic access.")

# ── Research agent works ──────────────────────────────────────────────
print("  ▸ Research agent: comparing auth providers...")
time.sleep(0.3)
do_tool(S, research_id, "Explore", "WebSearch", {"query": "NextAuth vs Clerk vs Auth0 Next.js 2024 comparison"},
    "Results: NextAuth is free/self-hosted, Clerk has best DX but $25/mo at scale, Auth0 enterprise pricing. Lucia is lightweight but manual setup.", 0.5)
do_tool(S, research_id, "Explore", "WebFetch", {"url": "https://authjs.dev/getting-started/introduction"},
    "Auth.js (NextAuth v5): Supports OAuth, magic links, credentials. Built-in adapters for Prisma, Drizzle. Edge runtime compatible. Free and open-source.", 0.4)
do_tool(S, research_id, "Explore", "WebSearch", {"query": "passkey authentication Next.js implementation WebAuthn"},
    "SimpleWebAuthn library + NextAuth custom provider. Passkeys supported in Chrome, Safari, Firefox. Recommended as MFA or passwordless option.", 0.4)
do_tool(S, research_id, "Explore", "WebFetch", {"url": "https://lucia-auth.com/getting-started/nextjs-app"},
    "Lucia: Lightweight auth library. Full control over sessions. No magic — you write the auth logic. Good for teams that want understanding, not abstraction.", 0.3)

time.sleep(0.2)
stop_agent(S, research_id, "Explore",
    "Recommendation: Use Auth.js (NextAuth v5) for OAuth + magic links. Self-hosted, free, Prisma adapter built-in. Add SimpleWebAuthn for passkey support as MFA. Avoid Clerk (vendor lock-in) and Auth0 (pricing). Lucia is good but too manual for our timeline.",
    research_tuid)
print("  ✓ Research complete")

# ── Security audit agent works ────────────────────────────────────────
print("  ▸ Security agent: auditing existing code...")
time.sleep(0.2)
do_tool(S, security_id, "Explore", "Read", {"file_path": "/Users/dev/projects/saas-platform/src/app/api/auth/[...nextauth]/route.ts"},
    'import NextAuth from "next-auth"\nimport GoogleProvider from "next-auth/providers/google"\n\nexport const authOptions = {\n  providers: [GoogleProvider({...})],\n  // WARNING: No session strategy defined — defaults to JWT\n  // WARNING: No CSRF token validation\n}', 0.3)
do_tool(S, security_id, "Explore", "Read", {"file_path": "/Users/dev/projects/saas-platform/src/middleware.ts"},
    'import { withAuth } from "next-auth/middleware"\nexport default withAuth({ pages: { signIn: "/login" } })\n// WARNING: No rate limiting\n// WARNING: No role-based route protection', 0.3)
do_tool(S, security_id, "Explore", "Grep", {"pattern": "bcrypt|argon2|scrypt|hashPassword", "glob": "**/*.ts"},
    "No matches found — no password hashing implementation exists", 0.2)
do_tool(S, security_id, "Explore", "Grep", {"pattern": "rateLimit|rate-limit|throttle", "glob": "**/*.ts"},
    "No matches found — no rate limiting configured", 0.2)
do_tool(S, security_id, "Explore", "Read", {"file_path": "/Users/dev/projects/saas-platform/next.config.js"},
    'module.exports = {\n  // No security headers configured\n  // No CSP policy\n}', 0.2)

time.sleep(0.2)
stop_agent(S, security_id, "Explore",
    "CRITICAL FINDINGS:\n1. No CSRF protection on auth endpoints\n2. No rate limiting — vulnerable to brute force\n3. No password hashing (credentials provider would store plaintext)\n4. No security headers (CSP, HSTS, X-Frame-Options)\n5. JWT session with no rotation strategy\n6. No role-based access control\n\nSeverity: HIGH — must fix before production.",
    security_tuid)
print("  ✓ Security audit complete — 6 critical findings")

# ── Plan agent works + spawns sub-agents (Layer 2) ────────────────────
print("  ▸ Plan agent: designing architecture...")
time.sleep(0.3)
do_tool(S, plan_id, "Plan", "Read", {"file_path": "/Users/dev/projects/saas-platform/prisma/schema.prisma"},
    'model User { id String @id @default(cuid()); email String @unique; ... }', 0.3)
do_tool(S, plan_id, "Plan", "Read", {"file_path": "/Users/dev/projects/saas-platform/src/lib/prisma.ts"},
    'import { PrismaClient } from "@prisma/client"\nconst prisma = new PrismaClient()\nexport default prisma', 0.2)

# Plan spawns implementation agents (Layer 2)
print("\n▸ Plan agent spawning 2 implementation agents...")
time.sleep(0.4)

backend_id, backend_tuid, _ = spawn_agent(S, plan_id, "Plan",
    "Implement auth backend",
    "general-purpose",
    "Implement the authentication backend:\n1. Upgrade to Auth.js v5 with Prisma adapter\n2. Add Google + GitHub OAuth providers\n3. Add magic link (email) provider\n4. Implement RBAC with admin/member/viewer roles\n5. Add API key model for programmatic access\n6. Add rate limiting middleware (10 req/min for auth endpoints)\n7. Add security headers (CSP, HSTS, X-Frame-Options)")

frontend_id, frontend_tuid, _ = spawn_agent(S, plan_id, "Plan",
    "Implement auth UI components",
    "general-purpose",
    "Build the authentication UI:\n1. Login page with OAuth buttons + magic link form\n2. Signup page with email/password + OAuth\n3. Profile settings page with MFA toggle\n4. Admin dashboard with user management table\n5. API key management page (create/revoke/list)\n6. Protected route wrapper component\n7. Role-based UI visibility (show/hide based on role)")

# ── Backend implementation agent works ────────────────────────────────
print("  ▸ Backend agent: implementing auth system...")
time.sleep(0.3)

# Update Prisma schema
do_tool(S, backend_id, "general-purpose", "Edit", {
    "file_path": "/Users/dev/projects/saas-platform/prisma/schema.prisma",
    "old_string": "model User {",
    "new_string": "enum Role {\n  ADMIN\n  MEMBER\n  VIEWER\n}\n\nmodel User {\n  role     Role @default(MEMBER)\n  apiKeys  ApiKey[]\n}\n\nmodel ApiKey {\n  id        String @id @default(cuid())\n  key       String @unique\n  name      String\n  userId    String\n  user      User @relation(fields: [userId])\n  createdAt DateTime @default(now())\n  lastUsed  DateTime?\n}"
}, "Edit applied — added Role enum, ApiKey model", 0.3)

do_tool(S, backend_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/saas-platform && npx prisma db push"},
    "Prisma schema pushed — 3 models updated, 1 enum created", 0.5)

# Auth.js v5 setup
do_tool(S, backend_id, "general-purpose", "Write", {
    "file_path": "/Users/dev/projects/saas-platform/src/lib/auth.ts",
    "content": "import NextAuth from 'next-auth'\nimport Google from 'next-auth/providers/google'\nimport GitHub from 'next-auth/providers/github'\nimport Email from 'next-auth/providers/email'\nimport { PrismaAdapter } from '@auth/prisma-adapter'\nimport prisma from './prisma'\n\nexport const { handlers, auth, signIn, signOut } = NextAuth({\n  adapter: PrismaAdapter(prisma),\n  providers: [Google, GitHub, Email({ server: process.env.SMTP_SERVER })],\n  session: { strategy: 'database', maxAge: 30 * 24 * 60 * 60 },\n  callbacks: {\n    session({ session, user }) {\n      session.user.role = user.role\n      return session\n    }\n  }\n})"
}, "File written — auth.ts with Auth.js v5 config", 0.3)

# Rate limiting
do_tool(S, backend_id, "general-purpose", "Write", {
    "file_path": "/Users/dev/projects/saas-platform/src/lib/rate-limit.ts",
    "content": "const rateLimitMap = new Map<string, { count: number; lastReset: number }>()\n\nexport function rateLimit(ip: string, limit = 10, windowMs = 60_000): boolean {\n  const now = Date.now()\n  const record = rateLimitMap.get(ip) ?? { count: 0, lastReset: now }\n  if (now - record.lastReset > windowMs) { record.count = 0; record.lastReset = now }\n  record.count++\n  rateLimitMap.set(ip, record)\n  return record.count <= limit\n}"
}, "File written — rate-limit.ts with sliding window", 0.3)

# Security middleware
do_tool(S, backend_id, "general-purpose", "Write", {
    "file_path": "/Users/dev/projects/saas-platform/src/middleware.ts",
    "content": "import { auth } from '@/lib/auth'\nimport { rateLimit } from '@/lib/rate-limit'\nimport { NextResponse } from 'next/server'\n\nexport default auth((req) => {\n  const ip = req.headers.get('x-forwarded-for') ?? '127.0.0.1'\n  if (req.nextUrl.pathname.startsWith('/api/auth') && !rateLimit(ip)) {\n    return new NextResponse('Too many requests', { status: 429 })\n  }\n  // Security headers\n  const res = NextResponse.next()\n  res.headers.set('X-Frame-Options', 'DENY')\n  res.headers.set('X-Content-Type-Options', 'nosniff')\n  res.headers.set('Strict-Transport-Security', 'max-age=31536000')\n  return res\n})"
}, "File written — middleware.ts with rate limiting + security headers", 0.3)

# API key implementation
do_tool(S, backend_id, "general-purpose", "Write", {
    "file_path": "/Users/dev/projects/saas-platform/src/app/api/keys/route.ts",
    "content": "import { auth } from '@/lib/auth'\nimport prisma from '@/lib/prisma'\nimport { randomBytes } from 'crypto'\n\nexport async function POST(req: Request) {\n  const session = await auth()\n  if (!session) return Response.json({ error: 'Unauthorized' }, { status: 401 })\n  const { name } = await req.json()\n  const key = `sk_${randomBytes(32).toString('hex')}`\n  const apiKey = await prisma.apiKey.create({ data: { key, name, userId: session.user.id } })\n  return Response.json({ id: apiKey.id, key, name: apiKey.name })\n}"
}, "File written — API key CRUD endpoints", 0.3)

# Run tests — first attempt fails
do_tool(S, backend_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/saas-platform && npm test -- --run src/lib/auth.test.ts"},
    "FAIL: auth.test.ts\n  ✗ should create session with database strategy\n    Error: PrismaClient not initialized in test environment\n  ✓ should include role in session callback\n  1 passed, 1 failed", 0.5, error=True)

# Fix and retry
do_tool(S, backend_id, "general-purpose", "Write", {
    "file_path": "/Users/dev/projects/saas-platform/src/lib/__mocks__/prisma.ts",
    "content": "import { PrismaClient } from '@prisma/client'\nimport { mockDeep } from 'jest-mock-extended'\n\nexport default mockDeep<PrismaClient>()"
}, "File written — Prisma mock for tests", 0.2)

do_tool(S, backend_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/saas-platform && npm test -- --run src/lib/auth.test.ts"},
    "PASS: auth.test.ts\n  ✓ should create session with database strategy (42ms)\n  ✓ should include role in session callback (12ms)\n  ✓ should enforce rate limiting (89ms)\n  ✓ should set security headers (15ms)\n  4 passed", 0.5)

# Backend spawns test writer (Layer 3!)
print("  ▸ Backend agent spawning test writer (3 layers deep)...")
time.sleep(0.3)

test_id, test_tuid, _ = spawn_agent(S, backend_id, "general-purpose",
    "Write E2E auth tests",
    "general-purpose",
    "Write end-to-end tests for the authentication system using Playwright:\n1. OAuth login flow (mock Google provider)\n2. Magic link signup and login\n3. Rate limiting enforcement\n4. Role-based route protection (admin vs member)\n5. API key creation and usage\n6. Session persistence across page reloads")

# ── Test writer works (Layer 3) ───────────────────────────────────────
time.sleep(0.2)
do_tool(S, test_id, "general-purpose", "Write", {
    "file_path": "/Users/dev/projects/saas-platform/e2e/auth.spec.ts",
    "content": "import { test, expect } from '@playwright/test'\n\ntest.describe('Authentication', () => {\n  test('OAuth login redirects to Google', async ({ page }) => {\n    await page.goto('/login')\n    await page.click('[data-testid=\"google-login\"]')\n    await expect(page).toHaveURL(/accounts\\.google\\.com/)\n  })\n\n  test('magic link sends email and logs in', async ({ page }) => {\n    await page.goto('/login')\n    await page.fill('[data-testid=\"email-input\"]', 'test@example.com')\n    await page.click('[data-testid=\"magic-link-button\"]')\n    await expect(page.locator('[data-testid=\"check-email\"]')).toBeVisible()\n  })\n\n  test('rate limiting blocks after 10 attempts', async ({ request }) => {\n    for (let i = 0; i < 11; i++) {\n      const res = await request.post('/api/auth/signin')\n      if (i === 10) expect(res.status()).toBe(429)\n    }\n  })\n\n  test('admin can access user management', async ({ page }) => {\n    await loginAsAdmin(page)\n    await page.goto('/admin/users')\n    await expect(page.locator('table')).toBeVisible()\n  })\n\n  test('member cannot access admin routes', async ({ page }) => {\n    await loginAsMember(page)\n    await page.goto('/admin/users')\n    await expect(page).toHaveURL('/unauthorized')\n  })\n\n  test('API key authenticates programmatic requests', async ({ request }) => {\n    const res = await request.get('/api/data', { headers: { Authorization: 'Bearer sk_test_...' } })\n    expect(res.ok()).toBe(true)\n  })\n})"
}, "File written — 6 E2E auth tests", 0.4)

do_tool(S, test_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/saas-platform && npx playwright test e2e/auth.spec.ts"},
    "Running 6 tests using 3 workers\n  ✓ OAuth login redirects to Google (1.2s)\n  ✓ magic link sends email and logs in (0.8s)\n  ✓ rate limiting blocks after 10 attempts (2.1s)\n  ✓ admin can access user management (0.9s)\n  ✓ member cannot access admin routes (0.7s)\n  ✓ API key authenticates programmatic requests (0.5s)\n\n6 passed (6.2s)", 0.6)

stop_agent(S, test_id, "general-purpose",
    "All 6 E2E tests passing: OAuth flow, magic links, rate limiting, RBAC route protection, API key auth, session persistence.",
    test_tuid)
print("  ✓ E2E tests complete (Layer 3)")

# ── Finish backend agent ──────────────────────────────────────────────
time.sleep(0.2)
stop_agent(S, backend_id, "general-purpose",
    "Auth backend complete:\n- Auth.js v5 with Google/GitHub/Email providers\n- Prisma adapter with RBAC (admin/member/viewer)\n- API key model with create/revoke endpoints\n- Rate limiting (10 req/min on auth endpoints)\n- Security headers (HSTS, X-Frame-Options, X-Content-Type-Options)\n- 4 unit tests + 6 E2E tests, all passing",
    backend_tuid)
print("  ✓ Backend implementation complete")

# ── Frontend implementation agent works ───────────────────────────────
print("  ▸ Frontend agent: building auth UI...")
time.sleep(0.3)

for component, content in [
    ("LoginPage.tsx", "OAuth buttons (Google/GitHub) + magic link email form + divider"),
    ("SignupPage.tsx", "Email/password form + OAuth buttons + terms checkbox"),
    ("ProfileSettings.tsx", "Avatar upload + name/email edit + MFA toggle + connected accounts"),
    ("AdminUserTable.tsx", "Sortable user table with role badges + invite button + search"),
    ("ApiKeyManager.tsx", "Create/revoke API keys + copy-to-clipboard + last used timestamp"),
    ("ProtectedRoute.tsx", "HOC wrapper checking session + role + redirect to /login or /unauthorized"),
]:
    do_tool(S, frontend_id, "general-purpose", "Write", {
        "file_path": f"/Users/dev/projects/saas-platform/src/components/auth/{component}",
        "content": f"// {component}\n// {content}\nexport default function {component.replace('.tsx', '')}() {{ ... }}"
    }, f"File written — {component}", 0.25)

do_tool(S, frontend_id, "general-purpose", "Edit", {
    "file_path": "/Users/dev/projects/saas-platform/src/app/layout.tsx",
    "old_string": "<body>",
    "new_string": "<SessionProvider><body>"
}, "Edit applied — wrapped app in SessionProvider", 0.2)

do_tool(S, frontend_id, "general-purpose", "Bash", {"command": "cd /Users/dev/projects/saas-platform && npm run build"},
    "✓ Compiled successfully\n  Route (app)           Size\n  ┌ /                   5.2 kB\n  ├ /login              3.1 kB\n  ├ /signup             3.4 kB\n  ├ /settings           4.8 kB\n  ├ /admin/users        6.2 kB\n  └ /api/keys           2.1 kB\n  First Load JS: 87.3 kB", 0.5)

stop_agent(S, frontend_id, "general-purpose",
    "Auth UI complete: LoginPage (OAuth + magic link), SignupPage, ProfileSettings (MFA toggle), AdminUserTable, ApiKeyManager, ProtectedRoute HOC. Build passes, total JS: 87.3 kB.",
    frontend_tuid)
print("  ✓ Frontend implementation complete")

# ── Finish plan agent ─────────────────────────────────────────────────
time.sleep(0.2)
stop_agent(S, plan_id, "Plan",
    "Architecture implemented:\n- Auth: Auth.js v5 + Prisma + 3 OAuth providers + magic links\n- Security: Rate limiting, CSRF protection, security headers\n- RBAC: Admin/Member/Viewer roles on User model\n- API: Key-based auth for programmatic access\n- UI: 6 components, all routes protected\n- Tests: 4 unit + 6 E2E, all green",
    plan_tuid)
print("  ✓ Plan agent complete")

# ── Root does final verification ──────────────────────────────────────
print("\n▸ Root agent: final verification...")
time.sleep(0.3)

do_tool(S, "", "", "Bash", {"command": "cd /Users/dev/projects/saas-platform && npm run build && npm test -- --run"},
    "Build: ✓ Compiled successfully\nTests: 10 passed, 0 failed\nE2E: 6 passed (6.2s)\nTotal: 16/16 passing", 0.6)

do_tool(S, "", "", "Bash", {"command": "cd /Users/dev/projects/saas-platform && git diff --stat"},
    " prisma/schema.prisma              | 18 ++++++++++\n src/lib/auth.ts                    | 24 +++++++++++++\n src/lib/rate-limit.ts              | 12 +++++++\n src/lib/__mocks__/prisma.ts        |  4 +++\n src/middleware.ts                  | 19 ++++++++---\n src/app/api/keys/route.ts          | 15 +++++++++\n src/components/auth/LoginPage.tsx   | 42 +++++++++++++++++++++\n src/components/auth/SignupPage.tsx  | 38 +++++++++++++++++++\n src/components/auth/ProfileSettings.tsx | 35 +++++++++++++++++\n src/components/auth/AdminUserTable.tsx  | 51 +++++++++++++++++++++++++\n src/components/auth/ApiKeyManager.tsx   | 33 ++++++++++++++++\n src/components/auth/ProtectedRoute.tsx  | 18 ++++++++++\n e2e/auth.spec.ts                   | 48 ++++++++++++++++++++++++\n 13 files changed, 355 insertions(+), 2 deletions(-)", 0.4)

# End session
time.sleep(0.3)
end_session(S)

print("\n" + "═" * 60)
print(f"  Demo complete!")
print(f"  8 agents · 3 layers deep · {S}")
print("═" * 60)
