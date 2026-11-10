import { UsersService, type UserPublic } from "@/client"

export type Permission = "users:read" | "users:manage" | "metrics:read"
export const can = (
  user: UserPublic | null | undefined,
  permission: Permission,
) => user?.permissions?.includes(permission) ?? false

export class AccessDeniedError extends Error {}

export async function requirePermission(permission: Permission) {
  const { data: user } = await UsersService.readUserMe()
  if (!can(user, permission)) throw new AccessDeniedError("Access denied")
}
