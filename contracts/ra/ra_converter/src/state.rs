use cosmwasm_schema::cw_serde;
use cosmwasm_std::Addr;
use cw_storage_plus::Item;

#[cw_serde]
pub struct Config {
    pub ra_cw20_addr: Addr,
    pub native_denom: String,
    pub fee_collector_addr: Addr,
    pub operator: Option<Addr>,
}

pub const CONFIG: Item<Config> = Item::new("config");
