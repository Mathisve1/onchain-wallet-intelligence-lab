# R11A resource-feasibility review

## Conclusion

The inert implementation has a bounded fail-closed execution design, but it does not pretend that a complete R11A result is guaranteed before the missing data properties are measured. The exact `tid` types, repeat multiplicities, schema-violation volume and repeated-block event volume were not retained by R11. Those unknowns are part of the R11A research question.

## Known source scale

The exact 72-object selection contains 2,107,738,436 compressed bytes. The original R11 artifact reports 10,539,979,245 decompressed bytes, 3,283,391 block observations and 26,384,234 event observations. R11A requires two deterministic local parses, producing a frozen processing ceiling of 21,079,958,490 decompressed bytes without issuing a second object request.

## Static workspace model

The implementation retains the 2.108 GB compressed selection temporarily and routes compact block and historical weak-key records into fixed 256-way partitions. At the exact observed source cardinalities:

- framed block index at 26 bytes per record: 85,368,166 bytes;
- representative integer-`tid` weak index at 96 bytes per event: 2,532,886,464 bytes;
- representative pre-sort total excluding schema-violation index: 4,725,993,066 bytes;
- frozen workspace cap: 5,368,709,120 bytes;
- representative margin before schema index and one-partition sort overhead: 642,716,054 bytes.

Only one partition is externally sorted at a time with a 64 MiB in-memory chunk. Completed index trees are removed before the second source pass. Compressed object files are deleted immediately after their second parse.

## Why success remains conditional

The 96-byte weak-index estimate describes the expected integer-`tid` path, not an unrestricted upper bound. The historical normalizer also recognizes nonempty strings up to 128 Unicode codepoints, and four-byte UTF-8 values can be materially larger. Schema violations and repeated-block membership are also data-dependent. The collector therefore measures allocated workspace continuously and stops without partial scientific output if the frozen cap is reached.

This is deliberate. A cap terminal is evidence that the preregistered retention design was insufficient; it is not permission to sample, truncate a group or silently raise a limit.

No sampling or silent cap increase is permitted.

## Atomicity and cleanup

The implementation uses append-only framed partitions, deterministic external sorting and an atomic staging directory. No scientific container is exposed until all required rows are sealed. A retention or artifact cap produces seven exact zero-byte scientific containers and a cap terminal. Other incomplete terminals also publish no partial scientific prefix. The forbidden wallet-feature file is always zero bytes.

The future network entrypoint checks for a separately merged exact single-use release before constructing any request. This D1 stage contains no installed workflow, owner approval, IAM mutation, OIDC assumption or S3 execution.

## Remaining proof

Synthetic and adversarial tests can prove deterministic serialization, taxonomy behavior, cap handling, cleanup and input-order invariance. They cannot reproduce the 21 GB wall-clock path or the unknown repeat volume. Those are empirical outputs of one separately approved R11A run. Consequently:

- bounded fail-closed execution: supported by the offline design;
- successful complete taxonomy within all caps: not yet empirically proven;
- R11 closure and R12 readiness: still false.
