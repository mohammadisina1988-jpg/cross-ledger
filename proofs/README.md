# Market proof plan

The live suite exercises crossing orders with partial fills and a post-settlement transfer; a noncrossing book with full reserve refunds; and blocked/uncertain descriptions that cannot supply tradable inventory. Three signing wallets are used per market. Raw/admitted/escrow inventory and quote-credit conservation are checked after every step.

The planned primary set has twenty-nine receipts across three independent markets, including two expected rejections. Finality, actual execution status, full votes, decoded calldata, participant signers, deployed code and full balance state must all verify before the suite is reported as complete. No ambiguous send is automatically repeated. Direct tests use web/model mocks while explicitly invoking validator callbacks.
