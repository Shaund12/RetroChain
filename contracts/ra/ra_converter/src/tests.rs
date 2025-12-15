use cosmwasm_std::{
    coin,
    testing::{mock_dependencies, mock_env, mock_info},
    Addr, BankMsg, CosmosMsg, WasmMsg,
};
use cw20::Cw20ExecuteMsg;

use crate::{
    contract,
    error::ContractError,
    msg::{ExecuteMsg, InstantiateMsg, QueryMsg},
};

fn instantiate_default() -> (
    cosmwasm_std::OwnedDeps<
        cosmwasm_std::testing::MockStorage,
        cosmwasm_std::testing::MockApi,
        cosmwasm_std::testing::MockQuerier,
    >,
    cosmwasm_std::Env,
) {
    let mut deps = mock_dependencies();
    let env = mock_env();
    let info = mock_info("creator", &[]);

    let msg = InstantiateMsg {
        ra_cw20_addr: "ratoken".to_string(),
        native_denom: "uretro".to_string(),
        fee_collector_addr: "feecollector".to_string(),
        operator: None,
    };

    let resp = contract::instantiate(deps.as_mut(), env.clone(), info, msg).unwrap();
    assert_eq!(resp.attributes.iter().any(|a| a.key == "action"), true);

    (deps, env)
}

#[test]
fn convert_requires_uretro_funds() {
    let (mut deps, env) = instantiate_default();

    let info = mock_info("alice", &[coin(123, "ubad")]);
    let err = contract::execute(deps.as_mut(), env.clone(), info, ExecuteMsg::Convert {}).unwrap_err();
    assert_eq!(err, ContractError::UnsupportedDenom {});

    let info = mock_info("alice", &[]);
    let err = contract::execute(deps.as_mut(), env, info, ExecuteMsg::Convert {}).unwrap_err();
    assert_eq!(err, ContractError::InvalidFunds {});
}

#[test]
fn convert_sends_native_and_mints_ra() {
    let (mut deps, env) = instantiate_default();

    let info = mock_info("alice", &[coin(10_000, "uretro")]);
    let resp = contract::execute(deps.as_mut(), env, info, ExecuteMsg::Convert {}).unwrap();
    assert_eq!(resp.messages.len(), 2);

    match &resp.messages[0].msg {
        CosmosMsg::Bank(BankMsg::Send { to_address, amount }) => {
            assert_eq!(to_address, "feecollector");
            assert_eq!(amount, &vec![coin(10_000, "uretro")]);
        }
        other => panic!("unexpected msg0: {other:?}"),
    }

    match &resp.messages[1].msg {
        CosmosMsg::Wasm(WasmMsg::Execute {
            contract_addr,
            msg,
            funds,
        }) => {
            assert_eq!(contract_addr, "ratoken");
            assert!(funds.is_empty());
            let parsed: Cw20ExecuteMsg = cosmwasm_std::from_json(msg).unwrap();
            assert_eq!(
                parsed,
                Cw20ExecuteMsg::Mint {
                    recipient: "alice".to_string(),
                    amount: 10_000u128.into(),
                }
            );
        }
        other => panic!("unexpected msg1: {other:?}"),
    }
}

#[test]
fn reward_mint_requires_operator_and_funding() {
    let (mut deps, env) = instantiate_default();

    // default operator is creator
    let info = mock_info("not_creator", &[coin(1, "uretro")]);
    let err = contract::execute(
        deps.as_mut(),
        env.clone(),
        info,
        ExecuteMsg::RewardMint {
            recipient: "bob".to_string(),
        },
    )
    .unwrap_err();
    assert_eq!(err, ContractError::Unauthorized {});

    let info = mock_info("creator", &[]);
    let err = contract::execute(
        deps.as_mut(),
        env.clone(),
        info,
        ExecuteMsg::RewardMint {
            recipient: "bob".to_string(),
        },
    )
    .unwrap_err();
    assert_eq!(err, ContractError::InvalidFunds {});

    let info = mock_info("creator", &[coin(7, "uretro")]);
    let resp = contract::execute(
        deps.as_mut(),
        env,
        info,
        ExecuteMsg::RewardMint {
            recipient: "bob".to_string(),
        },
    )
    .unwrap();

    // Mint should go to bob
    match &resp.messages[1].msg {
        CosmosMsg::Wasm(WasmMsg::Execute { msg, .. }) => {
            let parsed: Cw20ExecuteMsg = cosmwasm_std::from_json(msg).unwrap();
            assert_eq!(
                parsed,
                Cw20ExecuteMsg::Mint {
                    recipient: "bob".to_string(),
                    amount: 7u128.into(),
                }
            );
        }
        other => panic!("unexpected msg1: {other:?}"),
    }
}

#[test]
fn update_operator_changes_authority() {
    let (mut deps, env) = instantiate_default();

    let info = mock_info("creator", &[]);
    let resp = contract::execute(
        deps.as_mut(),
        env.clone(),
        info,
        ExecuteMsg::UpdateOperator {
            operator: Some("newop".to_string()),
        },
    )
    .unwrap();
    assert_eq!(resp.attributes[0].value, "update_operator");

    // old operator no longer works
    let info = mock_info("creator", &[coin(1, "uretro")]);
    let err = contract::execute(
        deps.as_mut(),
        env.clone(),
        info,
        ExecuteMsg::RewardMint {
            recipient: "bob".to_string(),
        },
    )
    .unwrap_err();
    assert_eq!(err, ContractError::Unauthorized {});

    // new operator works
    let info = mock_info("newop", &[coin(1, "uretro")]);
    let _resp = contract::execute(
        deps.as_mut(),
        env.clone(),
        info,
        ExecuteMsg::RewardMint {
            recipient: "bob".to_string(),
        },
    )
    .unwrap();

    // config query shows new operator
    let bin = contract::query(deps.as_ref(), env, QueryMsg::Config {}).unwrap();
    let resp: crate::msg::ConfigResponse = cosmwasm_std::from_json(bin).unwrap();
    assert_eq!(resp.operator, Some(Addr::unchecked("newop").to_string()));
}
