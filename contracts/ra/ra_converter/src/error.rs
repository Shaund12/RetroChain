use cosmwasm_std::StdError;
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum ContractError {
    #[error("{0}")]
    Std(#[from] StdError),

    #[error("unauthorized")]
    Unauthorized {},

    #[error("missing or invalid funds")]
    InvalidFunds {},

    #[error("unsupported denom")]
    UnsupportedDenom {},
}
