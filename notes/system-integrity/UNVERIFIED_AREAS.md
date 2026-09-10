# Unverified Areas

| Area | Reason | Required Evidence | Risk |
| --- | --- | --- | --- |
| Live LLM providers | Requires user credentials/network calls | Credentialed provider smoke tests | Provider-specific runtime drift |
| Full browser interaction | HTTP/build smoke tests do not exercise every browser interaction | Playwright or manual browser interaction test | UI wiring regressions |
| Real user vault | Repository safety rule avoids mutating user research data | Temporary vault plus optional user-approved vault dry run | Environment-specific path issues |
| Vector store | No implementation found | Design and implementation before runtime verification | Roadmap/spec mismatch |
| Runtime agents | No connected agent runtime found | Agent registry and action chain tests | Documentation may overstate capability |
