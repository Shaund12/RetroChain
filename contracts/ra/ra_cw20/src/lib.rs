// Thin wrapper around cw20-base so the chain can deploy a "RetroArcade" CW20
// from this repo without forking cw-plus.
//
// Configure name/symbol/decimals/marketing at instantiate time.

pub type InstantiateMsg = cw20_base::msg::InstantiateMsg;
pub type ExecuteMsg = cw20_base::msg::ExecuteMsg;
pub type QueryMsg = cw20_base::msg::QueryMsg;
pub type MigrateMsg = cw20_base::msg::MigrateMsg;

#[cfg(not(feature = "library"))]
mod entry {
    use super::*;
    use cosmwasm_std::{entry_point, Binary, Deps, DepsMut, Env, MessageInfo, Response, StdResult};

    #[entry_point]
    pub fn instantiate(
        deps: DepsMut,
        env: Env,
        info: MessageInfo,
        msg: InstantiateMsg,
    ) -> Result<Response, cw20_base::ContractError> {
        cw20_base::contract::instantiate(deps, env, info, msg)
    }

    #[entry_point]
    pub fn execute(
        deps: DepsMut,
        env: Env,
        info: MessageInfo,
        msg: ExecuteMsg,
    ) -> Result<Response, cw20_base::ContractError> {
        cw20_base::contract::execute(deps, env, info, msg)
    }

    #[entry_point]
    pub fn query(deps: Deps, env: Env, msg: QueryMsg) -> StdResult<Binary> {
        cw20_base::contract::query(deps, env, msg)
    }

    #[entry_point]
    pub fn migrate(deps: DepsMut, env: Env, msg: MigrateMsg) -> Result<Response, cw20_base::ContractError> {
        cw2::set_contract_version(deps.storage, "ra_cw20", "0.1.0")?;
        // cw20-base's migrate expects its own MigrateMsg type
        cw20_base::contract::migrate(deps, env, msg)
    }
}
