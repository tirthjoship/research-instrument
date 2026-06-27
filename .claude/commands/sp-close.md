# /sp-close — Close a completed sub-project

Run this command after an SP's PR merges to develop. Moves spec+plan to archive and updates all
living docs so future sessions start with accurate context.

## Usage

```
/sp-close SP=sp6
```

Or just `/sp-close` — Claude will ask which SP to close.

## Steps Claude must execute in order

1. **Identify the SP** — get the SP name/number from args or ask.

2. **Move spec + plan to archive**
   ```
   docs/superpowers/specs/*<sp>* → docs/superpowers/archive/
   docs/superpowers/plans/*<sp>* → docs/superpowers/archive/
   ```
   Use `git mv` so history is preserved.

3. **Update `docs/STATUS.md`**
   - Mark SP as ✅ merged in the SP Status table
   - Update "NEXT ACTION" to point at the next SP
   - Update branch name
   - Record key decisions/gotchas if any were discovered during implementation

4. **Update `README.md`**
   - Reflect any new user-facing features (new CLI commands, new dashboard tabs, new config)
   - Update "Current capabilities" or equivalent section
   - Do NOT add implementation detail — user-facing only

5. **Update `docs/PHASE_LOG.md`**
   - Append a brief entry under the relevant phase: what was built, what tests pass, key ADRs created
   - One paragraph max

6. **Update `CLAUDE.md` if needed**
   - Add new "do NOT auto-read" entries for any large generated files created by the SP
   - Add new gotchas to the "Gotchas" section if discovered
   - Update "Key Files — Where to Look" table if new packages were added

7. **Commit all doc updates**
   ```
   git add docs/ README.md CLAUDE.md
   git commit -m "docs: close SP<N> — archive spec+plan, update living docs"
   ```

8. **Confirm to user**
   Print summary: what was archived, what was updated, what's next.

## What NOT to do

- Do not delete spec/plan — `git mv` to archive, history preserved
- Do not update docs with implementation details — keep living docs user/session facing
- Do not run tests — this is a doc-only operation
- Do not push to remote — user pushes

## Archive location

`docs/superpowers/archive/` — tracked in git, never auto-read by Claude (see CLAUDE.md).
