# `.claude` — BruinBuddy Agentic Coding Architecture

This directory contains the complete agentic coding configuration for **BruinBuddy**, including specialized subagents, persistent per-agent memories, modular rules, slash commands, and our team Git collaboration playbook.

## Directory Structure

```text
.claude/
├── README.md                        # This architectural overview
├── COLLABORATION.md                 # End-to-end Git/GitHub workflow (Issue → Branch → PR → Merge)
├── settings.json                    # Shared Claude settings (human-only attribution, safe permissions)
├── launch.json                      # Local dev server launch configurations (real & mock LLM)
├── agents/                          # Specialized domain subagents
│   ├── git-workflow-manager.md      # Automates Issues, Branches, Commits, PRs & Merges for teammates
│   ├── backend-architect.md         # FastAPI, Supabase Auth, Stripe billing, tenancy & portable SQL
│   ├── ai-tutor-specialist.md       # RAG retrieval, problem set modes, leak guard & OpenRouter prompts
│   ├── frontend-developer.md        # React/Vite SPA, student chat SSE, staff console & UI components
│   ├── qa-security-auditor.md       # Pytest suite, security hardening, tenancy & leak guard verification
│   └── docs-maintainer.md           # Keeps docs/*.md, CLAUDE.md & agent memories synchronized
├── memory/                          # Persistent knowledge base & state per agent
│   ├── PROJECT_MEMORY.md            # Cross-cutting architectural decisions & project status
│   ├── git-workflow-manager.md      # Branch/PR history conventions & contributor identity notes
│   ├── backend-architect.md         # Schema tables, route dependencies, gates & billing invariants
│   ├── ai-tutor-specialist.md       # Retrieval pipeline, guard layers, modes & model cost tracking
│   ├── frontend-developer.md        # Route map, API wrapper patterns, SSE handling & design tokens
│   ├── qa-security-auditor.md       # Test fixtures, hardening regression inventory & audit checklist
│   └── docs-maintainer.md           # Documentation map & sync triggers
├── commands/                        # One-step slash commands for Claude Code (/project:<command>)
│   ├── start-task.md                # Create GitHub Issue + checkout linked feature branch
│   ├── ship.md                      # Test, commit (as human), push, create PR (Closes #N) & merge
│   ├── verify.md                    # Run full backend + frontend + security invariant verification
│   └── sync-memory.md               # Update agent memory files and docs after architectural changes
└── rules/                           # Modular guardrails loaded automatically
    ├── git-and-attribution.md       # Strict human-only contributor rule & Git workflow enforcement
    ├── backend-and-sql.md           # Tenancy, portable SQL, gates, Stripe & usage attribution rules
    ├── tutor-and-leak-guard.md      # Solution protection & academic integrity invariants
    └── frontend-conventions.md      # API wrapper, hash routing & student/staff data isolation
```

## How Agents & Memory Work Together

1. **Before Starting a Task:**
   - Every agent reads [CLAUDE.md](../CLAUDE.md), [.claude/COLLABORATION.md](COLLABORATION.md), and [.claude/memory/PROJECT_MEMORY.md](memory/PROJECT_MEMORY.md).
   - When a specialized subagent in `.claude/agents/<name>.md` is invoked, it first reads its dedicated memory file `.claude/memory/<name>.md` to load domain context, file maps, and past gotchas.
2. **During Execution:**
   - The `git-workflow-manager` (or main agent following `COLLABORATION.md`) ensures a GitHub Issue is created, a linked branch `<type>/issue-<N>-<slug>` is checked out, and all commits are authored strictly by the human developer (never Claude).
   - Domain agents implement and verify changes within their scope while respecting all 9 unbreakable rules in `CLAUDE.md`.
3. **After Completing a Task:**
   - The agent updates its `.claude/memory/<name>.md` (and `docs/` via `docs-maintainer`) if any new endpoints, tables, UI flows, or edge cases were introduced, before shipping the PR.
