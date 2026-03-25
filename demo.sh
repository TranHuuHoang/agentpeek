#!/bin/bash
# AgentPeek demo — complex multi-agent session with failures, retries, data passing
# Simulates a real Claude Code session: "Fix the authentication bug in the user service"

F="/tmp/agentpeek.jsonl"
S="demo-auth-fix"
CWD="/Users/dev/user-service"

emit() { echo "$1" >> "$F"; sleep "${2:-0.4}"; }

echo "Starting demo session: $S"
echo "Dashboard: http://localhost:8099"
echo ""

# ═══════════════════════════════════════════════════════════
# ROOT: Claude Code reads the issue and starts planning
# ═══════════════════════════════════════════════════════════

emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/src/auth/handler.py"},"tool_use_id":"r-t1","session_id":"'$S'","cwd":"'$CWD'"}'
sleep 0.8
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"class AuthHandler:\n    def login(self, username, password):\n        user = self.db.find_user(username)\n        if not user or not verify_hash(password, user.password_hash):\n            raise AuthError(\"Invalid credentials\")\n        token = jwt.encode({\"sub\": user.id, \"exp\": datetime.now() + timedelta(hours=1)})\n        return {\"token\": token, \"user_id\": user.id}\n\n    def refresh_token(self, token):\n        # BUG: doesn'\''t check if token is expired before refreshing\n        payload = jwt.decode(token)\n        return jwt.encode({\"sub\": payload[\"sub\"], \"exp\": datetime.now() + timedelta(hours=1)})","tool_use_id":"r-t1","session_id":"'$S'"}'
sleep 0.3

emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/src/auth/middleware.py"},"tool_use_id":"r-t2","session_id":"'$S'","cwd":"'$CWD'"}'
sleep 0.5
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"from auth.handler import AuthHandler\n\ndef require_auth(func):\n    def wrapper(request):\n        token = request.headers.get(\"Authorization\")\n        if not token:\n            return Response(401)\n        try:\n            payload = jwt.decode(token)\n            request.user_id = payload[\"sub\"]\n        except jwt.ExpiredTokenError:\n            return Response(401, \"Token expired\")\n        return func(request)\n    return wrapper","tool_use_id":"r-t2","session_id":"'$S'"}'

# ═══════════════════════════════════════════════════════════
# SPAWN: explore_codebase — find all auth-related code
# ═══════════════════════════════════════════════════════════

emit '{"hook":"PreToolUse","tool_name":"Agent","tool_input":{"description":"explore_codebase","subagent_type":"Explore","prompt":"Find all authentication-related files, test files, and JWT usage across the codebase. Report which files handle tokens."},"tool_use_id":"r-t3","session_id":"'$S'"}'
sleep 0.2
emit '{"hook":"SubagentStart","agent_id":"a-explore","agent_type":"Explore","tool_use_id":"r-t3","session_id":"'$S'"}'

# Explore: grep for auth patterns
emit '{"hook":"PreToolUse","tool_name":"Grep","tool_input":{"pattern":"jwt\\.encode|jwt\\.decode|AuthHandler"},"tool_use_id":"e-t1","session_id":"'$S'","agent_id":"a-explore"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Grep","tool_response":"src/auth/handler.py:12: token = jwt.encode(...)\nsrc/auth/handler.py:18: payload = jwt.decode(token)\nsrc/auth/middleware.py:9: payload = jwt.decode(token)\nsrc/api/routes.py:34: from auth.handler import AuthHandler\ntests/test_auth.py:5: from auth.handler import AuthHandler","tool_use_id":"e-t1","session_id":"'$S'","agent_id":"a-explore"}' 0.6

# Explore: read test file
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/tests/test_auth.py"},"tool_use_id":"e-t2","session_id":"'$S'","agent_id":"a-explore"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"import pytest\nfrom auth.handler import AuthHandler\n\nclass TestAuth:\n    def test_login_success(self):\n        handler = AuthHandler(mock_db)\n        result = handler.login(\"admin\", \"password123\")\n        assert \"token\" in result\n\n    def test_login_bad_password(self):\n        handler = AuthHandler(mock_db)\n        with pytest.raises(AuthError):\n            handler.login(\"admin\", \"wrong\")","tool_use_id":"e-t2","session_id":"'$S'","agent_id":"a-explore"}' 0.5

# Explore: try reading config — FAILS (permission)
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/config/jwt_secrets.yaml"},"tool_use_id":"e-t3","session_id":"'$S'","agent_id":"a-explore"}' 0.3
emit '{"hook":"PostToolUseFailure","tool_name":"Read","tool_response":"Error: Permission denied. File /config/jwt_secrets.yaml is outside allowed directory.","tool_use_id":"e-t3","session_id":"'$S'","agent_id":"a-explore"}' 0.4

# Explore: retry with correct path
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/src/config/settings.py"},"tool_use_id":"e-t4","session_id":"'$S'","agent_id":"a-explore"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"JWT_SECRET = os.environ.get(\"JWT_SECRET\", \"dev-secret\")\nJWT_EXPIRY_HOURS = 1\nJWT_REFRESH_WINDOW = 300  # seconds before expiry when refresh is allowed","tool_use_id":"e-t4","session_id":"'$S'","agent_id":"a-explore"}' 0.5

# Explore: read routes
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/src/api/routes.py"},"tool_use_id":"e-t5","session_id":"'$S'","agent_id":"a-explore"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"from auth.handler import AuthHandler\nfrom auth.middleware import require_auth\n\n@app.post(\"/login\")\ndef login(request):\n    return auth.login(request.json[\"username\"], request.json[\"password\"])\n\n@app.post(\"/refresh\")\n@require_auth\ndef refresh(request):\n    return auth.refresh_token(request.headers[\"Authorization\"])","tool_use_id":"e-t5","session_id":"'$S'","agent_id":"a-explore"}' 0.4

# Explore done
emit '{"hook":"SubagentStop","agent_id":"a-explore","session_id":"'$S'","result":"Found 5 auth-related files. JWT used in handler.py and middleware.py. Bug confirmed: refresh_token() doesn'\''t validate expiry. Config shows JWT_REFRESH_WINDOW=300s. Test coverage exists but no refresh token tests.","tool_use_id":"r-t3"}' 0.3

# ═══════════════════════════════════════════════════════════
# SPAWN: plan_implementation — design the fix
# ═══════════════════════════════════════════════════════════

emit '{"hook":"PreToolUse","tool_name":"Agent","tool_input":{"description":"plan_implementation","subagent_type":"Plan","prompt":"Design fix for auth bug. Explore found: refresh_token() in handler.py doesn'\''t check expiry before refreshing. Config has JWT_REFRESH_WINDOW=300s. Need to: 1) Fix handler.py refresh_token to validate expiry window 2) Add tests for refresh edge cases 3) Update middleware if needed. Files: handler.py, middleware.py, settings.py, test_auth.py, routes.py"},"tool_use_id":"r-t4","session_id":"'$S'"}'
sleep 0.2
emit '{"hook":"SubagentStart","agent_id":"a-plan","agent_type":"Plan","tool_use_id":"r-t4","session_id":"'$S'"}'

# Plan reads handler to understand current code
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/src/auth/handler.py"},"tool_use_id":"p-t1","session_id":"'$S'","agent_id":"a-plan"}' 0.4
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"class AuthHandler:\n    def refresh_token(self, token):\n        # BUG: doesn'\''t check expiry\n        payload = jwt.decode(token)\n        return jwt.encode({\"sub\": payload[\"sub\"], ...})","tool_use_id":"p-t1","session_id":"'$S'","agent_id":"a-plan"}' 0.5

# Plan reads settings
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/src/config/settings.py"},"tool_use_id":"p-t2","session_id":"'$S'","agent_id":"a-plan"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"JWT_REFRESH_WINDOW = 300","tool_use_id":"p-t2","session_id":"'$S'","agent_id":"a-plan"}' 0.4

# ═══════════════════════════════════════════════════════════
# Plan SPAWNS: write_fix — implement the handler fix
# ═══════════════════════════════════════════════════════════

emit '{"hook":"PreToolUse","tool_name":"Agent","tool_input":{"description":"write_fix","subagent_type":"general-purpose","prompt":"Fix refresh_token() in /src/auth/handler.py. Add expiry validation: decode token, check if current time is within JWT_REFRESH_WINDOW (300s) of expiry. If token expired beyond window, raise AuthError. Import settings.JWT_REFRESH_WINDOW."},"tool_use_id":"p-t3","session_id":"'$S'","agent_id":"a-plan"}'
sleep 0.2
emit '{"hook":"SubagentStart","agent_id":"a-fix","agent_type":"general-purpose","tool_use_id":"p-t3","session_id":"'$S'"}'

# write_fix reads the file
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/src/auth/handler.py"},"tool_use_id":"f-t1","session_id":"'$S'","agent_id":"a-fix"}' 0.4
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"class AuthHandler:\n    def refresh_token(self, token):\n        payload = jwt.decode(token)\n        return jwt.encode({\"sub\": payload[\"sub\"], \"exp\": datetime.now() + timedelta(hours=1)})","tool_use_id":"f-t1","session_id":"'$S'","agent_id":"a-fix"}' 0.6

# write_fix edits handler — FAILS first attempt (wrong import)
emit '{"hook":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"/src/auth/handler.py","old_string":"def refresh_token","new_string":"def refresh_token_fixed"},"tool_use_id":"f-t2","session_id":"'$S'","agent_id":"a-fix"}' 0.3
emit '{"hook":"PostToolUseFailure","tool_name":"Edit","tool_response":"Error: old_string not found in file. The file may have been modified. Re-read and try again.","tool_use_id":"f-t2","session_id":"'$S'","agent_id":"a-fix"}' 0.5

# write_fix re-reads and retries
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/src/auth/handler.py"},"tool_use_id":"f-t3","session_id":"'$S'","agent_id":"a-fix"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"class AuthHandler:\n    def refresh_token(self, token):\n        payload = jwt.decode(token)\n        return jwt.encode(...)","tool_use_id":"f-t3","session_id":"'$S'","agent_id":"a-fix"}' 0.4

# write_fix edits handler — succeeds
emit '{"hook":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"/src/auth/handler.py","old_string":"    def refresh_token(self, token):\n        payload = jwt.decode(token)","new_string":"    def refresh_token(self, token):\n        from config.settings import JWT_REFRESH_WINDOW\n        try:\n            payload = jwt.decode(token, options={\"verify_exp\": False})\n        except jwt.InvalidTokenError:\n            raise AuthError(\"Invalid token\")\n        exp = datetime.fromtimestamp(payload[\"exp\"])\n        if datetime.now() > exp + timedelta(seconds=JWT_REFRESH_WINDOW):\n            raise AuthError(\"Token expired beyond refresh window\")"},"tool_use_id":"f-t4","session_id":"'$S'","agent_id":"a-fix"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Edit","tool_response":"Successfully edited /src/auth/handler.py","tool_use_id":"f-t4","session_id":"'$S'","agent_id":"a-fix"}' 0.6

# write_fix done
emit '{"hook":"SubagentStop","agent_id":"a-fix","session_id":"'$S'","result":"Fixed refresh_token() in handler.py. Added expiry window validation using JWT_REFRESH_WINDOW from settings. Handles InvalidTokenError. Required 1 retry due to stale file content.","tool_use_id":"p-t3"}' 0.3

# ═══════════════════════════════════════════════════════════
# Plan SPAWNS: write_tests — add test coverage
# ═══════════════════════════════════════════════════════════

emit '{"hook":"PreToolUse","tool_name":"Agent","tool_input":{"description":"write_tests","subagent_type":"general-purpose","prompt":"Write tests for the fixed refresh_token() in /src/auth/handler.py. Cover: 1) refresh valid token within window 2) reject expired token beyond window 3) reject invalid/malformed token 4) refresh at exact boundary. Add to /tests/test_auth.py."},"tool_use_id":"p-t4","session_id":"'$S'","agent_id":"a-plan"}'
sleep 0.2
emit '{"hook":"SubagentStart","agent_id":"a-tests","agent_type":"general-purpose","tool_use_id":"p-t4","session_id":"'$S'"}'

# write_tests reads existing tests
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/tests/test_auth.py"},"tool_use_id":"w-t1","session_id":"'$S'","agent_id":"a-tests"}' 0.4
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"import pytest\nfrom auth.handler import AuthHandler\n\nclass TestAuth:\n    def test_login_success(self): ...\n    def test_login_bad_password(self): ...","tool_use_id":"w-t1","session_id":"'$S'","agent_id":"a-tests"}' 0.5

# write_tests reads fixed handler
emit '{"hook":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"/src/auth/handler.py"},"tool_use_id":"w-t2","session_id":"'$S'","agent_id":"a-tests"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Read","tool_response":"class AuthHandler:\n    def refresh_token(self, token):\n        from config.settings import JWT_REFRESH_WINDOW\n        payload = jwt.decode(token, options={\"verify_exp\": False})\n        exp = datetime.fromtimestamp(payload[\"exp\"])\n        if datetime.now() > exp + timedelta(seconds=JWT_REFRESH_WINDOW):\n            raise AuthError(\"Token expired beyond refresh window\")\n        return jwt.encode(...)","tool_use_id":"w-t2","session_id":"'$S'","agent_id":"a-tests"}' 0.6

# write_tests writes the test file
emit '{"hook":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"/tests/test_auth.py"},"tool_use_id":"w-t3","session_id":"'$S'","agent_id":"a-tests"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Edit","tool_response":"Added 4 new test methods:\n    def test_refresh_valid_token(self):\n        token = make_token(exp=datetime.now() + timedelta(minutes=2))\n        result = handler.refresh_token(token)\n        assert \"token\" in result\n\n    def test_refresh_expired_beyond_window(self):\n        token = make_token(exp=datetime.now() - timedelta(hours=1))\n        with pytest.raises(AuthError, match=\"beyond refresh window\"):\n            handler.refresh_token(token)\n\n    def test_refresh_invalid_token(self):\n        with pytest.raises(AuthError, match=\"Invalid token\"):\n            handler.refresh_token(\"not.a.real.token\")\n\n    def test_refresh_at_boundary(self):\n        token = make_token(exp=datetime.now() - timedelta(seconds=299))\n        result = handler.refresh_token(token)\n        assert \"token\" in result","tool_use_id":"w-t3","session_id":"'$S'","agent_id":"a-tests"}' 0.8

# write_tests adds conftest fixture
emit '{"hook":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"/tests/conftest.py"},"tool_use_id":"w-t4","session_id":"'$S'","agent_id":"a-tests"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Edit","tool_response":"Added make_token() fixture and mock_db fixture","tool_use_id":"w-t4","session_id":"'$S'","agent_id":"a-tests"}' 0.4

# write_tests runs pytest — FAILS
emit '{"hook":"PreToolUse","tool_name":"Bash","tool_input":{"command":"cd /Users/dev/user-service && python -m pytest tests/test_auth.py -v"},"tool_use_id":"w-t5","session_id":"'$S'","agent_id":"a-tests"}' 0.3
emit '{"hook":"PostToolUseFailure","tool_name":"Bash","tool_response":"FAILED tests/test_auth.py::TestAuth::test_refresh_at_boundary - AssertionError: AuthError raised unexpectedly. Off-by-one: token at 299s should be within 300s window but timedelta comparison is strict >","tool_use_id":"w-t5","session_id":"'$S'","agent_id":"a-tests"}' 1.0

# write_tests fixes the boundary condition in handler
emit '{"hook":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"/src/auth/handler.py"},"tool_use_id":"w-t6","session_id":"'$S'","agent_id":"a-tests"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Edit","tool_response":"Fixed off-by-one: changed > to >= in expiry comparison","tool_use_id":"w-t6","session_id":"'$S'","agent_id":"a-tests"}' 0.5

# write_tests re-runs pytest — PASSES
emit '{"hook":"PreToolUse","tool_name":"Bash","tool_input":{"command":"cd /Users/dev/user-service && python -m pytest tests/test_auth.py -v"},"tool_use_id":"w-t7","session_id":"'$S'","agent_id":"a-tests"}' 0.3
emit '{"hook":"PostToolUse","tool_name":"Bash","tool_response":"tests/test_auth.py::TestAuth::test_login_success PASSED\ntests/test_auth.py::TestAuth::test_login_bad_password PASSED\ntests/test_auth.py::TestAuth::test_refresh_valid_token PASSED\ntests/test_auth.py::TestAuth::test_refresh_expired_beyond_window PASSED\ntests/test_auth.py::TestAuth::test_refresh_invalid_token PASSED\ntests/test_auth.py::TestAuth::test_refresh_at_boundary PASSED\n\n6 passed in 0.42s","tool_use_id":"w-t7","session_id":"'$S'","agent_id":"a-tests"}' 1.0

# write_tests done
emit '{"hook":"SubagentStop","agent_id":"a-tests","session_id":"'$S'","result":"Added 4 refresh token tests. Found and fixed off-by-one boundary bug in handler.py (> to >=). All 6 tests passing.","tool_use_id":"p-t4"}' 0.3

# Plan done
emit '{"hook":"SubagentStop","agent_id":"a-plan","session_id":"'$S'","result":"Auth fix complete. 1) Fixed refresh_token() with expiry window validation 2) Added 4 test cases 3) Fixed off-by-one boundary bug found during testing. All 6 tests pass.","tool_use_id":"r-t4"}' 0.3

echo ""
echo "Demo session complete! Open http://localhost:8099"
echo "Click on different agents to explore the execution traces."
