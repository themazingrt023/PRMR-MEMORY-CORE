# Architecture

The RC1 command and runtime layers delegate to the authoritative Core 1-13 services. The stable internal flow is source ledger -> candidate extraction -> explicit admission -> bitemporal ledger -> temporal dynamics -> entity/relationship memory -> deterministic query -> optional exact consolidation -> governed export and continuity packets.

`prmr.release.PRMRMemoryCore` is the supported RC facade. Repository helpers remain test-only. Bounded interpretation proposals are not truth; assertions, derivations, tentative inferences, unknowns, and conflicts remain distinct in Packet V2.

Supported runtime modes are `sqlite_local` and `postgres_single_node`. This does not imply multi-region operation, automatic failover, zero downtime, or distributed consensus.
