// Use the public signup contract; no unauthenticated admin helper is exposed.
import { UsersService } from "../../src/client"
import { client } from "../../src/client/client.gen"

client.setConfig({
  baseURL: `${process.env.VITE_API_URL}`,
})

export const createUser = async ({
  email,
  password,
}: {
  email: string
  password: string
}) => {
  const response = await UsersService.registerUser({
    body: {
      email,
      password,
      full_name: "Test User",
    },
  })
  return response.data
}
