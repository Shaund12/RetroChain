use cosmwasm_std::{
    entry_point, to_json_binary, Addr, BankMsg, Binary, Coin, Deps, DepsMut, Env, MessageInfo,
    Response, StdError, StdResult, Uint128,
};
use cw2::set_contract_version;
use cw_storage_plus::{Item, Map};
use serde::{Deserialize, Serialize};

const CONTRACT_NAME: &str = "ra_claimdrop";
const CONTRACT_VERSION: &str = "0.1.0";

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct InstantiateMsg {
    pub admin: String,
    pub denom: String,
    pub claim_amount: Uint128,
    pub total_amount: Uint128,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ExecuteMsg {
    /// Free-for-all claim: one claim per RetroChain address, first-come-first-served.
    Claim { recipient: Option<String> },
    UpdateConfig {
        admin: Option<String>,
        denom: Option<String>,
        claim_amount: Option<Uint128>,
        total_amount: Option<Uint128>,
    },
    Withdraw {
        recipient: String,
        amount: Option<Coin>,
    },
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum QueryMsg {
    Config {},
    IsClaimed { address: String },
    Stats {},
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct Config {
    pub admin: Addr,
    pub denom: String,
    pub claim_amount: Uint128,
    pub total_amount: Uint128,
    pub max_claims: u64,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct StatsResponse {
    pub claimed_count: u64,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq)]
pub struct IsClaimedResponse {
    pub is_claimed: bool,
}

#[derive(thiserror::Error, Debug, PartialEq)]
pub enum ContractError {
    #[error("{0}")]
    Std(#[from] StdError),

    #[error("unauthorized")]
    Unauthorized,

    #[error("invalid denom")]
    InvalidDenom,

    #[error("claim amount must be > 0")]
    InvalidClaimAmount,

    #[error("total amount must be > 0")]
    InvalidTotalAmount,

    #[error("total amount must be divisible by claim amount")]
    TotalNotDivisible,

    #[error("already claimed")]
    AlreadyClaimed,

    #[error("claim cap reached")]
    CapReached,
}

const CONFIG: Item<Config> = Item::new("config");
const CLAIMED: Map<&Addr, bool> = Map::new("claimed");
const CLAIMED_COUNT: Item<u64> = Item::new("claimed_count");

#[entry_point]
pub fn instantiate(
    deps: DepsMut,
    _env: Env,
    _info: MessageInfo,
    msg: InstantiateMsg,
) -> Result<Response, ContractError> {
    set_contract_version(deps.storage, CONTRACT_NAME, CONTRACT_VERSION)?;

    let admin = deps.api.addr_validate(&msg.admin)?;

    if msg.denom.trim().is_empty() {
        return Err(ContractError::InvalidDenom);
    }
    if msg.claim_amount.is_zero() {
        return Err(ContractError::InvalidClaimAmount);
    }
    if msg.total_amount.is_zero() {
        return Err(ContractError::InvalidTotalAmount);
    }
    if msg.total_amount.u128() % msg.claim_amount.u128() != 0 {
        return Err(ContractError::TotalNotDivisible);
    }

    let max_claims = (msg.total_amount.u128() / msg.claim_amount.u128()) as u64;

    let cfg = Config {
        admin,
        denom: msg.denom,
        claim_amount: msg.claim_amount,
        total_amount: msg.total_amount,
        max_claims,
    };

    CONFIG.save(deps.storage, &cfg)?;
    CLAIMED_COUNT.save(deps.storage, &0u64)?;

    Ok(Response::new())
}

#[entry_point]
pub fn execute(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> Result<Response, ContractError> {
    match msg {
        ExecuteMsg::Claim { recipient } => execute_claim(deps, info, recipient),
        ExecuteMsg::UpdateConfig {
            admin,
            denom,
            claim_amount,
            total_amount,
        } => execute_update_config(deps, info, admin, denom, claim_amount, total_amount),
        ExecuteMsg::Withdraw { recipient, amount } => execute_withdraw(deps, env, info, recipient, amount),
    }
}

fn execute_claim(
    deps: DepsMut,
    info: MessageInfo,
    recipient: Option<String>,
) -> Result<Response, ContractError> {
    let cfg = CONFIG.load(deps.storage)?;

    let recipient = match recipient {
        Some(r) => deps.api.addr_validate(&r)?,
        None => info.sender,
    };

    if CLAIMED.may_load(deps.storage, &recipient)?.unwrap_or(false) {
        return Err(ContractError::AlreadyClaimed);
    }

    let mut claimed_count = CLAIMED_COUNT.load(deps.storage)?;
    if claimed_count >= cfg.max_claims {
        return Err(ContractError::CapReached);
    }

    CLAIMED.save(deps.storage, &recipient, &true)?;
    claimed_count = claimed_count.saturating_add(1);
    CLAIMED_COUNT.save(deps.storage, &claimed_count)?;

    let send = BankMsg::Send {
        to_address: recipient.to_string(),
        amount: vec![Coin {
            denom: cfg.denom,
            amount: cfg.claim_amount,
        }],
    };

    Ok(Response::new().add_message(send))
}

fn execute_update_config(
    deps: DepsMut,
    info: MessageInfo,
    admin: Option<String>,
    denom: Option<String>,
    claim_amount: Option<Uint128>,
    total_amount: Option<Uint128>,
) -> Result<Response, ContractError> {
    CONFIG.update(deps.storage, |mut cfg| {
        if info.sender != cfg.admin {
            return Err(ContractError::Unauthorized);
        }

        if let Some(admin) = admin {
            cfg.admin = deps.api.addr_validate(&admin)?;
        }
        if let Some(denom) = denom {
            if denom.trim().is_empty() {
                return Err(ContractError::InvalidDenom);
            }
            cfg.denom = denom;
        }

        let mut new_claim_amount = cfg.claim_amount;
        let mut new_total_amount = cfg.total_amount;

        if let Some(a) = claim_amount {
            if a.is_zero() {
                return Err(ContractError::InvalidClaimAmount);
            }
            new_claim_amount = a;
        }
        if let Some(t) = total_amount {
            if t.is_zero() {
                return Err(ContractError::InvalidTotalAmount);
            }
            new_total_amount = t;
        }

        if new_total_amount.u128() % new_claim_amount.u128() != 0 {
            return Err(ContractError::TotalNotDivisible);
        }

        cfg.claim_amount = new_claim_amount;
        cfg.total_amount = new_total_amount;
        cfg.max_claims = (new_total_amount.u128() / new_claim_amount.u128()) as u64;

        Ok(cfg)
    })?;

    Ok(Response::new())
}

fn execute_withdraw(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    recipient: String,
    amount: Option<Coin>,
) -> Result<Response, ContractError> {
    let cfg = CONFIG.load(deps.storage)?;
    if info.sender != cfg.admin {
        return Err(ContractError::Unauthorized);
    }

    let recipient = deps.api.addr_validate(&recipient)?;

    let send_amount = match amount {
        Some(coin) => vec![coin],
        None => {
            let balance = deps
                .querier
                .query_balance(env.contract.address.to_string(), cfg.denom)?;
            if balance.amount.is_zero() {
                return Ok(Response::new());
            }
            vec![balance]
        }
    };

    let msg = BankMsg::Send {
        to_address: recipient.to_string(),
        amount: send_amount,
    };

    Ok(Response::new().add_message(msg))
}

#[entry_point]
pub fn query(deps: Deps, _env: Env, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::Config {} => to_json_binary(&CONFIG.load(deps.storage)?),
        QueryMsg::IsClaimed { address } => {
            let addr = deps.api.addr_validate(&address)?;
            let is_claimed = CLAIMED.may_load(deps.storage, &addr)?.unwrap_or(false);
            to_json_binary(&IsClaimedResponse { is_claimed })
        }
        QueryMsg::Stats {} => {
            let claimed_count = CLAIMED_COUNT.load(deps.storage)?;
            to_json_binary(&StatsResponse { claimed_count })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cosmwasm_std::testing::{mock_dependencies, mock_env, mock_info};

    #[test]
    fn instantiate_and_claim_once() {
        let mut deps = mock_dependencies();

        let msg = InstantiateMsg {
            admin: "cosmos1adminxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx".to_string(),
            denom: "uretro".to_string(),
            claim_amount: Uint128::new(2_500_000_000),
            total_amount: Uint128::new(5_000_000_000),
        };

        instantiate(deps.as_mut(), mock_env(), mock_info("anyone", &[]), msg).unwrap();

        let res = execute(
            deps.as_mut(),
            mock_env(),
            mock_info("cosmos1claimerxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", &[]),
            ExecuteMsg::Claim { recipient: None },
        )
        .unwrap();

        assert_eq!(res.messages.len(), 1);

        let err = execute(
            deps.as_mut(),
            mock_env(),
            mock_info("cosmos1claimerxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", &[]),
            ExecuteMsg::Claim { recipient: None },
        )
        .unwrap_err();
        assert_eq!(err, ContractError::AlreadyClaimed);
    }
}
