# Writer / Authority Registration Registry

This registry is the explicit architecture decision boundary for new
writer/store/repository/authority implementations. It is intentionally exact:
one path and symbol per row, with a named owner and a decision/reference ID.
Adding a row does not grant runtime authority by itself; it records the review
that approved the implementation and its single owner.

| Path | Symbol | Owner | Architecture decision |
| --- | --- | --- | --- |
