export interface ShareResource {
  kind: string;
  id: string;
  name: string;
  workspace_id: string;
  workspace_name?: string;
}
export interface ResourceShare {
  id: string;
  kind: string;
  resource_id: string;
  name: string;
  target_id: string;
  target_name: string;
  access: string;
}
export interface WorkspaceShares {
  resources: ShareResource[];
  native?: ShareResource[];
  targets: { id: string; name: string }[];
  outgoing: ResourceShare[];
  incoming: ResourceShare[];
}
export const resourceKey = (item: { kind: string; id: string }) =>
  `${item.kind}:${item.id}`;
