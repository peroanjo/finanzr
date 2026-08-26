import { config } from "@vue/test-utils";
import { beforeEach } from "vitest";
import { applyLocale, i18n, registerMessages } from "../i18n";
import { coreMessages } from "../i18n/coreMessages";
import { viewMessagesA } from "../i18n/viewMessagesA";
import { cryptoMessages } from "../i18n/cryptoMessages";
import { fundsMessages } from "../i18n/fundsMessages";
import { stocksMessages } from "../i18n/stocksMessages";
import { sharedMessages } from "../i18n/sharedMessages";
import { apiMessages } from "../i18n/apiMessages";

registerMessages(coreMessages);
registerMessages(viewMessagesA);
registerMessages(fundsMessages);
registerMessages(stocksMessages);
registerMessages(cryptoMessages);
registerMessages(sharedMessages);
registerMessages(apiMessages);
config.global.plugins = [i18n];

beforeEach(() => {
  applyLocale("es-ES");
});
