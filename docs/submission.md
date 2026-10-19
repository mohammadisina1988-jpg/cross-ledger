Category: Builder → Intelligent Contracts

Title: CrossLedger: Consensus-screened native batch exchange

Description:

CrossLedger is a bounded two-sided GenLayer call market. Leader and validators independently fetch hash-pinned lot descriptions, derive every PASS/FAIL/UNKNOWN class decision and audit source clauses. Only all-PASS raw units become tradable inventory. Signed ASK orders escrow units; BID orders reserve quantity times limit credits. After participants seal, clearing maximizes traded volume, minimizes imbalance and applies an explicit price tie-break, then settles every fill at one price with price/time priority. Unfilled inventory and excess reserves return atomically. Owners may cancel before sealing or abort before clearing; purchased units can transfer afterward. Tests include independent exhaustive feasible-fill searches and conservation checks. Fixtures represent abstract native units and newly endowed quote credits, not GEN, money, external property or verified delivery. The repository documents source authority, veto/Sybil limits and consensus failure cases.

Repository: https://github.com/mohammadisina1988-jpg/cross-ledger
Contract source: https://github.com/mohammadisina1988-jpg/cross-ledger/blob/main/contracts/cross_ledger.py
Proofs: https://github.com/mohammadisina1988-jpg/cross-ledger/blob/main/proofs/README.md
