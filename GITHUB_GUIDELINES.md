# GitHub Guidelines — Sewdoo

Conventions for branch naming, commit messages, pull requests, and code review across all module repositories.

---

## 1. Branch Strategy

| Branch | Purpose | Who can push directly |
|--------|---------|----------------------|
| `19.0` | Production — live client deployments | Admin only, via PR |
| `release` | Staging / final UAT before production | Senior Devs, via PR |
| `develop` | Active development integration | All contributors |
| `feature/*` | New features and experimental work | Assigned contributor |
| `bugfix/*` | Bug fixes targeting develop | Assigned contributor |
| `hotfix/*` | Critical fixes that must go to production immediately | Senior Dev only |

### Naming Format

```
feature/<module>-<short-description>
bugfix/<module>-<short-description>
hotfix/<module>-<short-description>
```

**Examples:**
```
feature/hr_recruitment-add-assessment-gate
bugfix/attendance-fix-duplicate-punch-removal
hotfix/payroll-critical-epf-calculation-error
```

**Rules:**
- Always lowercase, hyphen-separated — no spaces, no underscores in the description part
- Always include the module name so the scope is clear at a glance
- Keep the description under 5 words
- Branch off `develop` for features and bugfixes
- Branch off `main` for hotfixes only

---

## 2. Commit Messages

### Format

```
[TAG] <module>: short imperative description
```

### Tags

| Tag | Use for |
|-----|---------|
| `[ADD]` | New models, views, fields, wizards, or features |
| `[FIX]` | Bug fixes |
| `[IMP]` | Improvements to existing functionality |
| `[REF]` | Refactoring — no functional change |
| `[REM]` | Removing code, fields, or features |
| `[MOV]` | Moving or renaming files / modules |
| `[I18N]` | Translation file updates |
| `[MIG]` | Odoo version migration changes |

### Examples

```
[ADD] hr_onboarding: add QR-coded employee ID card generation
[FIX] attendance: correct 20-minute OT block exclusion logic
[IMP] payroll: refactor base salary divisor selection by contract type
[REF] mrp_operation_template: decouple template picker into wizard
[REM] hr_recruitment: remove legacy applicant scoring model
[I18N] attendance: add Sinhala translations for leave types
```

### Rules

- Use the imperative mood — "add", not "added" or "adds"
- No period at the end of the subject line
- Subject line must be ≤ 72 characters
- Reference the issue number in the commit body when applicable: `Closes #42`

---

## 3. Pull Request Process

### Opening a PR

1. Ensure your branch is up to date with its base branch (`git pull origin develop`)
2. Run `make check` locally — all checks must pass before opening the PR
3. Fill in the PR template completely; incomplete descriptions will be sent back
4. Set the correct base branch:
   - Normal work → `develop`
   - Hotfixes → `19.0` (then back-port to `develop` via a second PR)
5. Link the related issue: `Closes #<number>`
6. Assign at least one Senior Developer as reviewer

### PR Title

Match the commit format exactly:
```
[ADD] hr_recruitment: add assessment gate model
```

### Merge Requirements

| Requirement | enforce |
|-------------|---------|
| All CI checks green (ruff, pylint-odoo) | ✅ Required |
| At least 1 Senior Developer approval | ✅ Required |
| No unresolved review comments | ✅ Required |
| Branch up to date with base | ✅ Required |

### Merge Strategy

- **Feature / bugfix → `develop`**: Squash and merge (keeps history clean)
- **`develop` → `release` → `19.0`**: Merge commit (preserves release structure)
- Delete the source branch after merge

---

## 4. Hotfix Process

For critical bugs that need to reach production without waiting for the normal release cycle:

```bash
# 1. Branch from main (not develop)
git checkout 19.0
git pull origin 19.0
git checkout -b hotfix/<module>-<description>

# 2. Fix, commit, push
git commit -m "[FIX] <module>: <short description>"
git push origin hotfix/<module>-<description>

# 3. Open PR: hotfix/* → main
# 4. After merge to main, immediately open a second PR: main → develop
#    This keeps develop in sync with the production fix.
```

---

## 5. Code Review Checklist

Reviewers should verify all of the following before approving:

**Odoo conventions**
- [ ] All user-facing strings wrapped in `_()`
- [ ] No business logic in `__init__.py`
- [ ] Computed fields use `@api.depends` (not `@api.onchange` where avoidable)
- [ ] `domain` filters on fields preferred over Python-side filtering

**Security**
- [ ] `ir.model.access.csv` updated for every new model
- [ ] `ir.rule` record rules added where row-level access control is needed
- [ ] No SQL built by string concatenation (use ORM or parameterised queries)

**Quality**
- [ ] No `print()`, `import pdb`, or other debug statements
- [ ] No hardcoded database IDs or environment-specific values
- [ ] Tests included for new models, constraints, and workflow transitions

---

## 6. Protected Branch Rules

| Rule | `19.0` | `release` | `develop` |
|------|:------:|:---------:|:---------:|
| Direct push blocked | ✅ | ✅ | ❌ |
| Pull Request required | ✅ | ✅ | ❌ |
| 1 Senior Dev approval required | ✅ | ✅ | ❌ |
| CI must pass before merge | ✅ | ✅ | ✅ |

Protection is enforced at two layers:
1. **Local** — the `scripts/pre-push` hook (installed by `make setup`) blocks pushes before they leave your machine
2. **GitHub** — branch protection rules on the remote reject any push that bypasses the local hook

---

*Maintained by Beaver Hub (Pvt) Ltd*
