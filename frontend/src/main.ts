import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";
import { i18n, registerMessages } from "./i18n";
import { coreMessages } from "./i18n/coreMessages";
import { viewMessagesA } from "./i18n/viewMessagesA";
import { cryptoMessages } from "./i18n/cryptoMessages";
import { fundsMessages } from "./i18n/fundsMessages";
import { stocksMessages } from "./i18n/stocksMessages";
import { sharedMessages } from "./i18n/sharedMessages";
import { apiMessages } from "./i18n/apiMessages";
import { currenciesMessages } from "./i18n/currenciesMessages";
import "@fontsource-variable/manrope";
import "./style.css";

registerMessages(coreMessages);
registerMessages(viewMessagesA);
registerMessages(fundsMessages);
registerMessages(stocksMessages);
registerMessages(cryptoMessages);
registerMessages(sharedMessages);
registerMessages(apiMessages);
registerMessages(currenciesMessages);

createApp(App).use(createPinia()).use(i18n).use(router).mount("#app");
