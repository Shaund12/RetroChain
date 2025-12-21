import { GeneratedType } from "@cosmjs/proto-signing";
import { MsgUpdateParams } from "./types/retrochain/arcade/v1/tx";
import { MsgInsertCoin } from "./types/retrochain/arcade/v1/tx";
import { MsgSubmitScore } from "./types/retrochain/arcade/v1/tx";
import { MsgStartSession } from "./types/retrochain/arcade/v1/tx";

const msgTypes: Array<[string, GeneratedType]>  = [
    ["/retrochain.arcade.v1.MsgUpdateParams", MsgUpdateParams],
    ["/retrochain.arcade.v1.MsgInsertCoin", MsgInsertCoin],
    ["/retrochain.arcade.v1.MsgSubmitScore", MsgSubmitScore],
    ["/retrochain.arcade.v1.MsgStartSession", MsgStartSession],
    
];

export { msgTypes }