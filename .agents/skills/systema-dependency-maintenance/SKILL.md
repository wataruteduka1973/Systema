---
name: systema-dependency-maintenance
description: Assess and implement safe dependency upgrades for Systema. Use when updating Python packages, GitHub Actions, frontend or documentation dependencies, or when investigating advisories and compatibility constraints.
---

# Systema Dependency Maintenance

Treat an upgrade as a scoped compatibility and security change, not routine version replacement. Inspect the direct declaration, lock/pin style, imports and APIs used, supported Python/Django versions, release notes or advisory evidence, and CI/runtime impact before editing.

Prefer the smallest supported upgrade that resolves the stated issue. Do not add a package when the standard library or an existing dependency already satisfies the requirement. Preserve environment-neutral configuration and never add credentials or registry tokens.

Classify the change as patch, minor, major, security-driven, or transitive. For breaking or security-sensitive upgrades, identify behavior changes, deprecated APIs, configuration changes, and rollback constraints. Use current primary-source release/advisory documentation when network access is available; otherwise mark compatibility conclusions that depend on it as `NOT VERIFIED`.

Update all authoritative declarations that the repository intentionally keeps aligned, without opportunistically upgrading unrelated packages. Add or adjust regression tests for behavior touched by the dependency. Run the matching focused `manage.py verify` suite plus the formatter/linter/type/documentation/build checks affected by the upgrade. Use full verification only at a Phase boundary or when the dependency has genuinely repository-wide impact.

Report the old/new version, reason, compatibility evidence, files changed, verification performed, and remaining rollout or production checks. Never claim CI or production compatibility from local checks alone.
