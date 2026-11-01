import { defineMessageCatalog } from "./catalog";
export const workspaceMessages = defineMessageCatalog(
  {
    workspace: {
      title: "Workspaces",
      subtitle: "Personal and shared spaces",
      personal: "Personal",
      shared: "Shared",
      scopeHelp:
        "Only members can access this workspace. Shared resources keep their original owner and history.",
      name: "Workspace name",
      rename: "Rename",
      members: "Members",
      memberRole: "Role for {name}",
      roles: { owner: "Owner", editor: "Editor", viewer: "Viewer" },
      leave: "Leave workspace",
      remove: "Remove member",
      inviteEmail: "Invite by email",
      permission: "Permission",
      invite: "Create invitation",
      inviteCreated:
        "Send this invitation code privately to the recipient. It expires after 7 days and only that email can accept it.",
      cancelInvite: "Cancel invitation",
      create: "Create shared workspace",
      createHelp:
        "Creates an empty workspace in your current reporting currency. Your personal assets remain private.",
      invitationCode: "Invitation code",
      accept: "Accept invitation",
      shareAssets: "Share accounts and assets",
      shareHelp:
        "Share the original record without copying it. A shared account includes its full history and future movements. Only its owning workspace can delete it. Both spaces must use the same reporting currency.",
      resource: "Account or asset",
      choose: "Choose…",
      target: "Shared workspace",
      read: "Read only",
      edit: "Can edit",
      share: "Share / update access",
      outgoing: "Resources you share",
      incoming: "Resources shared with this workspace",
      revoke: "Revoke access",
      archive: "Archive workspace",
      archiveHelp:
        "Hides this shared workspace for all members. Original assets shared from other spaces remain in their owning workspace.",
      archiveConfirm:
        "I want to archive this shared workspace for all members.",
      failure:
        "The action could not be completed. Check your permissions, the invitation code or reporting currencies. A workspace must retain at least one owner.",
      loading: "Loading…",
      kinds: {
        account: "Account",
        manual_asset: "Manual asset",
        real_estate: "Real estate",
      },
    },
  },
  {
    workspace: {
      title: "Espacios",
      subtitle: "Espacios privados y compartidos",
      personal: "Personal",
      shared: "Compartido",
      scopeHelp:
        "Solo los miembros pueden acceder a este espacio. Los elementos compartidos conservan su propietario e historial originales.",
      name: "Nombre del espacio",
      rename: "Cambiar nombre",
      members: "Miembros",
      memberRole: "Permisos de {name}",
      roles: { owner: "Propietario", editor: "Editor", viewer: "Lector" },
      leave: "Salir del espacio",
      remove: "Quitar miembro",
      inviteEmail: "Invitar por correo",
      permission: "Permisos",
      invite: "Crear invitación",
      inviteCreated:
        "Envía este código en privado al destinatario. Caduca en 7 días y solo puede aceptarlo ese correo.",
      cancelInvite: "Cancelar invitación",
      create: "Crear espacio compartido",
      createHelp:
        "Crea un espacio vacío con tu moneda de referencia actual. Tus activos personales siguen siendo privados.",
      invitationCode: "Código de invitación",
      accept: "Aceptar invitación",
      shareAssets: "Compartir cuentas y activos",
      shareHelp:
        "Comparte el registro original sin copiarlo. Una cuenta compartida incluye todo su historial y los movimientos futuros. Solo puede eliminarse desde su espacio propietario. Ambos espacios deben tener la misma moneda de referencia.",
      resource: "Cuenta o activo",
      choose: "Seleccionar…",
      target: "Espacio compartido",
      read: "Solo lectura",
      edit: "Puede editar",
      share: "Compartir / actualizar permisos",
      outgoing: "Elementos que compartes",
      incoming: "Elementos compartidos con este espacio",
      revoke: "Revocar acceso",
      archive: "Archivar espacio",
      archiveHelp:
        "Oculta este espacio compartido para todos sus miembros. Los activos compartidos desde otros espacios se conservan en su espacio propietario.",
      archiveConfirm:
        "Quiero archivar este espacio compartido para todos sus miembros.",
      failure:
        "No se ha podido completar la acción. Revisa los permisos, el código de invitación o las monedas de referencia. Debe quedar al menos un propietario.",
      loading: "Cargando…",
      kinds: {
        account: "Cuenta",
        manual_asset: "Activo manual",
        real_estate: "Inmueble",
      },
    },
  },
);
