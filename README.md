# CrossLedger

GenLayer **consensus-screened uniform-price call market** with actual contract-native inventory and quote-credit settlement. Independently verified lot descriptions determine which raw units enter the tradable class. Participants sign limit orders that escrow admitted units or quote credits. Clearing changes balances atomically, refunds unused reserves and preserves both asset totals. Purchased units can subsequently be transferred among the configured participants.

The contract fetches every committed source document inside the nondeterministic flow. Validators independently derive every positive, negative and uncertain criterion decision, require exact decision equality, and audit every cited clause against full source context. An all-PASS lot converts raw inventory into admitted units; FAIL blocks it, UNKNOWN leaves it in REVIEW. Titles, hashes and nonempty text never determine admission by themselves.

The bounded price rule maximizes executable volume, minimizes demand/supply imbalance, then chooses the lowest integer price. Better limit prices precede worse ones; order ID breaks equal-price ties. Each participant takes one side per batch and seals its own book. A participant may abort before settlement to refund all open escrow. No administrator can rewrite source commitments, endowments or criteria.

These are abstract native units and newly endowed quote credits. They are not GEN, cash, externally backed vouchers, physical property or proof of service delivery. Document consensus interprets the published descriptions; it does not establish offchain truth, issuer identity or enforceability. All live fixtures and wallets are controlled demonstrations.

## Check

```sh
pip install -r requirements-dev.txt
genvm-lint download --version v0.2.16
genvm-lint check contracts/cross_ledger.py --json
node --test tests/rpc-preflight.test.cjs
python -m pytest tests/direct -q
```

The 70 direct tests explicitly run validator callbacks, check reserve refunds and ownership enforcement, enumerate all 1,296 small four-order books against exhaustive feasible-fill searches, and exercise 48 generated books with cancellations. A separate JavaScript per-unit ticket oracle replays actual direct-mode states and the live traces. Seven transport tests ensure read-only gas-price retries never replay signed sends. Direct-mode web/model responses are mocked; live receipts test actual consensus.

[Contract](contracts/cross_ledger.py) · [Design and limits](docs/design.md) · [Proofs](proofs/README.md) · [Submission text](docs/submission.md).

StudioNet: [contract explorer](https://explorer-studio.genlayer.com/address/0xb80E123816d7b52d581b0cE4d806073A2bC4BfAE). Three markets on the current source have twenty-nine finalized majority-agreement receipts, including two expected rejections. Complete traces verify partial fills, excess-reserve refunds, a buyer's native-unit transfer, noncrossing refunds and blocked/uncertain source descriptions. All receipts, actual signers/calldata, full votes, exact code and current balances pass independent offline and fresh verification. Earlier-source successes and the rejected UNKNOWN attempt remain available separately.

Uniform-price auctions are established mechanisms. [Deutsche Börse's auction overview](https://www.cashmarket.deutsche-boerse.com/cash-en/trading/Xetra/continuous-trading-with-auctions) describes maximum executable volume and minimum overhang. CrossLedger uses its own bounded price grid and lowest-price final tie-break; it does not reproduce an exchange's full rulebook or claim incentive compatibility. The new code is the native lot conversion, signed book controller, escrow settlement and independent market oracles. Generic CLI journaling, receipt decoding, encrypted CI-wallet setup and the Windows test workaround reuse attributed MIT infrastructure from EndowSwap and its predecessors.
