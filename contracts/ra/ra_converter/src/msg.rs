use cosmwasm_schema::{cw_serde, QueryResponses};

#[cw_serde]
pub struct InstantiateMsg {
    /// CW20 contract address for RA token.
    pub ra_cw20_addr: String,

    /// The native denom accepted for conversion (must be `uretro`).
    pub native_denom: String,

    /// Address that receives the full native deposit.
    /// Set this to the chain's fee collector module address so that:
    /// - `x/burn` burns ~80% each block
    /// - remaining ~20% is distributed to stakers
    pub fee_collector_addr: String,

    /// Optional operator who can mint rewards (must still provide native funds).
    pub operator: Option<String>,
}

#[cw_serde]
pub enum ExecuteMsg {
    /// Convert attached `native_denom` funds 1:1 into RA CW20 and forward funds to fee collector.
    Convert {},

    /// Mint RA as a reward. Caller must be `operator` and must attach funds of `native_denom`.
    /// This still routes the native to fee collector (burn+stakers) and mints RA 1:1.
    RewardMint { recipient: String },

    /// Update operator (only current operator).
    UpdateOperator { operator: Option<String> },
}

#[cw_serde]
#[derive(QueryResponses)]
pub enum QueryMsg {
    #[returns(ConfigResponse)]
    Config {},
}

#[cw_serde]
pub struct ConfigResponse {
    pub ra_cw20_addr: String,
    pub native_denom: String,
    pub fee_collector_addr: String,
    pub operator: Option<String>,
}
