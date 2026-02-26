---
created: 2026-02-18T15:22:16.585Z
title: django-cubano wrapper
area: api
files: []
---

## Problem

Django projects that use Cubano must manually manage engine registration and lifecycle (calling `cubano.register()` / `cubano.unregister()` themselves). There's no idiomatic Django integration — no settings-based configuration, no AppConfig lifecycle hooks, no DRF serializer support, and no admin interface for exploring semantic views.

A `django-cubano` package would make Cubano feel native to Django projects, similar to how `django-redis` wraps Redis or `django-extensions` wraps common utilities.

This was explicitly deferred from v0.1 scope as a separate package for a later milestone.

## Solution

TBD — separate package (`django-cubano`, not part of the core `cubano` repo). Likely provides:
- `CUBANO` settings dict in `settings.py` for engine registration (similar to Django `DATABASES`)
- `CubanoAppConfig` that calls `cubano.register()` on `AppConfig.ready()`
- Optional DRF serializer mixin for returning `Result` objects as JSON
- Possibly a Django admin view for ad-hoc querying of registered semantic views
