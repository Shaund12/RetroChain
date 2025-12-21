// Thin wrapper around cw721-base so the chain can deploy an NFT contract
// from this repo without forking cw-plus.
//
// Configure name/symbol/minter at instantiate time.

pub type InstantiateMsg = cw721_base::msg::InstantiateMsg;
pub type ExecuteMsg = cw721_base::msg::ExecuteMsg<cw721_base::Extension, cosmwasm_std::Empty>;
pub type QueryMsg = cw721_base::msg::QueryMsg<cosmwasm_std::Empty>;

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
    ) -> StdResult<Response> {
        cw721_base::entry::instantiate(deps, env, info, msg)
    }

    #[entry_point]
    pub fn execute(
        deps: DepsMut,
        env: Env,
        info: MessageInfo,
        msg: ExecuteMsg,
    ) -> Result<Response, cw721_base::ContractError> {
        cw721_base::entry::execute(deps, env, info, msg)
    }

    #[entry_point]
    pub fn query(deps: Deps, env: Env, msg: QueryMsg) -> StdResult<Binary> {
        cw721_base::entry::query(deps, env, msg)
    }
}
