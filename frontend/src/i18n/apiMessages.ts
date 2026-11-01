import { defineMessageCatalog } from "./catalog";

export const apiMessages = defineMessageCatalog(
  {
    apiClient: {
      secureSessionError: "A secure session could not be started",
      workspaceChanged:
        "The active workspace changed. Reload before continuing.",
    },
  },
  {
    apiClient: {
      secureSessionError: "No se pudo iniciar una sesión segura",
      workspaceChanged:
        "El espacio activo ha cambiado. Recarga antes de continuar.",
    },
  },
);
