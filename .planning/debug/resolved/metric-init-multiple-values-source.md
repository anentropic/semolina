---
status: resolved
trigger: "TypeError: Field.__init__() got multiple values for argument 'source' when calling Metric('order_id', source='ORDER_ID')"
created: 2026-02-25T00:00:00Z
updated: 2026-02-25T21:00:00Z
---

## Current Focus

hypothesis: Field.__init__ signature has `source` as the sole positional parameter, so passing a name string positionally fills `source`, then the explicit `source=` kwarg conflicts with it
test: Inspect Field.__init__ signature and trace call Metric('order_id', source='ORDER_ID')
expecting: 'order_id' binds to `source` positionally, then source='ORDER_ID' causes the conflict
next_action: confirm signature and document root cause

## Symptoms

expected: Metric('order_id', source='ORDER_ID') constructs a Metric with name='order_id' and source='ORDER_ID'
actual: TypeError: Field.__init__() got multiple values for argument 'source'
errors: "TypeError: Field.__init__() got multiple values for argument 'source'"
reproduction: from cubano.fields import Metric; Metric('order_id', source='ORDER_ID')
started: unknown / design-time issue

## Eliminated

(none yet)

## Evidence

- timestamp: 2026-02-25T00:00:00Z
  checked: src/cubano/fields.py Field.__init__ signature (line 117)
  found: "def __init__(self, source: str | None = None) -> None:" — only parameter is `source`
  implication: Metric('order_id', source='ORDER_ID') binds 'order_id' positionally to `source`, then source='ORDER_ID' is also passed for `source`, causing the conflict

- timestamp: 2026-02-25T00:00:00Z
  checked: Metric and Dimension class bodies (lines 635-654)
  found: Both are bare `pass` — they inherit Field.__init__ directly with no override
  implication: The bug is solely in Field.__init__ lacking a `name` parameter

- timestamp: 2026-02-25T00:00:00Z
  checked: All usages of Metric() across codebase
  found: Every usage is either Metric() with no args, or Metric(source="...") with keyword arg only — none pass a positional name string
  implication: The API as-designed and as-documented does NOT accept a positional name; the user call pattern Metric('order_id', source='ORDER_ID') assumes a name parameter that does not exist

- timestamp: 2026-02-25T00:00:00Z
  checked: Field.__repr__ (lines 248-254) and Field.__set_name__ (lines 138-194)
  found: self.name is always set by __set_name__ (called by Python when field is assigned to class attribute), never via __init__
  implication: The design intent is that name comes from the class attribute assignment, not from a constructor argument. There is no legitimate way to pass a name at construction time.

- timestamp: 2026-02-25T00:00:00Z
  checked: Bug reproduction via uv run python
  found: Bug is 100% reproducible; exact error matches report
  implication: Root cause confirmed

## Resolution

root_cause: >
  Field.__init__(self, source=None) accepts only one parameter, `source`. When a user calls
  Metric('order_id', source='ORDER_ID'), Python binds the positional argument 'order_id' to
  `source` (the only positional slot), then sees source='ORDER_ID' as a second binding for
  the same parameter, raising TypeError. The class has no `name` parameter at all — field
  names are always set by Python's descriptor protocol (__set_name__) when the field is
  assigned as a class attribute.

fix: (not applied — diagnosis only)
verification: (not applied — diagnosis only)
files_changed: []
