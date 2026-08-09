# R8B cutover forensics

Static, no-network study of the `node_fills` → `node_fills_by_block` archive boundary.

Canonical conclusion: the shared `2025-07-27T08` path hour is a transition boundary with high-confidence separate within-hour coverage/cutover semantics, but exact event-time partitioning is not directly proven. The fail-closed project rule is therefore to censor that shared boundary hour when building a cross-format history.

This study opens no data-access, performance-analysis, ranking, copyability or trading authority.
