import { defineMessageCatalog } from "./catalog";

export const apiMessages = defineMessageCatalog(
  {
    apiClient: {
      secureSessionError: "A secure session could not be started",
    },
  },
  {
    apiClient: {
      secureSessionError: "No se pudo iniciar una sesión segura",
    },
  },
);
