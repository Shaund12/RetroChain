# Retrochain Testnet (local)

This folder is intended for running a second `retrochaind` instance locally ("testnet") alongside your main node.

- Default GUI `--home`: `testnet/home`
- Recommended: use different ports than mainnet (RPC/API/gRPC/P2P).

In the GUI Node Manager, use the **Testnet** tab:
- **Clone config from main** to copy `config/` files (does not copy `data/`).
- **Apply ports** to write the port overrides into `testnet/home/config/config.toml` and `testnet/home/config/app.toml`.
- Then **Start**.
