use cosmwasm_std::{
    to_json_binary, BankMsg, Binary, Deps, DepsMut, Env, MessageInfo, Response, StdResult, WasmMsg,
};
use cw2::set_contract_version;
use cw20::Cw20ExecuteMsg;

use crate::error::ContractError;
use crate::msg::{ConfigResponse, ExecuteMsg, InstantiateMsg, QueryMsg};
use crate::state::{Config, CONFIG};

const CONTRACT_NAME: &str = "ra_converter";
const CONTRACT_VERSION: &str = "0.1.0";

pub fn instantiate(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    msg: InstantiateMsg,
) -> Result<Response, ContractError> {
    set_contract_version(deps.storage, CONTRACT_NAME, CONTRACT_VERSION)?;

    let ra_cw20_addr = deps.api.addr_validate(&msg.ra_cw20_addr)?;
    let fee_collector_addr = deps.api.addr_validate(&msg.fee_collector_addr)?;

    let operator = match msg.operator {
        Some(op) => Some(deps.api.addr_validate(&op)?),
        None => Some(info.sender.clone()),
    };

    let cfg = Config {
        ra_cw20_addr,
        native_denom: msg.native_denom,
        fee_collector_addr,
        operator,
    };

    CONFIG.save(deps.storage, &cfg)?;

    Ok(Response::new()
        .add_attribute("action", "instantiate")
        .add_attribute("native_denom", cfg.native_denom)
        .add_attribute("ra_cw20_addr", cfg.ra_cw20_addr.to_string())
        .add_attribute("fee_collector_addr", cfg.fee_collector_addr.to_string()))
}

pub fn execute(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> Result<Response, ContractError> {
    match msg {
        ExecuteMsg::Convert {} => execute_convert(deps, info, None),
        ExecuteMsg::RewardMint { recipient } => execute_reward_mint(deps, info, recipient),
        ExecuteMsg::UpdateOperator { operator } => execute_update_operator(deps, info, operator),
    }
}

fn extract_amount(info: &MessageInfo, denom: &str) -> Result<u128, ContractError> {
    let mut amt: u128 = 0;
    for c in &info.funds {
        if c.denom == denom {
            amt = amt.saturating_add(c.amount.u128());
        } else if c.amount.u128() > 0 {
            // any other denom attached is rejected
            return Err(ContractError::UnsupportedDenom {});
        }
    }
    if amt == 0 {
        return Err(ContractError::InvalidFunds {});
    }
    Ok(amt)
}

fn execute_convert(
    deps: DepsMut,
    info: MessageInfo,
    recipient_override: Option<String>,
) -> Result<Response, ContractError> {
    let cfg = CONFIG.load(deps.storage)?;
    let amt = extract_amount(&info, &cfg.native_denom)?;

    let recipient = match recipient_override {
        Some(r) => deps.api.addr_validate(&r)?,
        None => info.sender.clone(),
    };

    // Send all incoming native to fee collector.
    let send_native = BankMsg::Send {
        to_address: cfg.fee_collector_addr.to_string(),
        amount: info.funds.clone(),
    };

    // Mint RA 1:1 to the recipient.
    let mint = WasmMsg::Execute {
        contract_addr: cfg.ra_cw20_addr.to_string(),
        msg: to_json_binary(&Cw20ExecuteMsg::Mint {
            recipient: recipient.to_string(),
            amount: amt.into(),
        })?,
        funds: vec![],
    };

    Ok(Response::new()
        .add_message(send_native)
        .add_message(mint)
        .add_attribute("action", "convert")
        .add_attribute("recipient", recipient.to_string())
        .add_attribute("amount", amt.to_string())
        .add_attribute("denom", cfg.native_denom))
}

fn execute_reward_mint(
    deps: DepsMut,
    info: MessageInfo,
    recipient: String,
) -> Result<Response, ContractError> {
    let cfg = CONFIG.load(deps.storage)?;
    let operator = cfg.operator.clone().ok_or(ContractError::Unauthorized {})?;
    if info.sender != operator {
        return Err(ContractError::Unauthorized {});
    }

    execute_convert(deps, info, Some(recipient))
}

fn execute_update_operator(
    deps: DepsMut,
    info: MessageInfo,
    operator: Option<String>,
) -> Result<Response, ContractError> {
    CONFIG.update(deps.storage, |mut cfg| -> Result<_, ContractError> {
        let current = cfg.operator.clone().ok_or(ContractError::Unauthorized {})?;
        if info.sender != current {
            return Err(ContractError::Unauthorized {});
        }
        cfg.operator = match operator {
            Some(op) => Some(deps.api.addr_validate(&op)?),
            None => None,
        };
        Ok(cfg)
    })?;

    Ok(Response::new().add_attribute("action", "update_operator"))
}

pub fn query(deps: Deps, _env: Env, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::Config {} => to_json_binary(&query_config(deps)?),
    }
}

fn query_config(deps: Deps) -> StdResult<ConfigResponse> {
    let cfg = CONFIG.load(deps.storage)?;
    Ok(ConfigResponse {
        ra_cw20_addr: cfg.ra_cw20_addr.to_string(),
        native_denom: cfg.native_denom,
        fee_collector_addr: cfg.fee_collector_addr.to_string(),
        operator: cfg.operator.map(|a| a.to_string()),
    })
}
