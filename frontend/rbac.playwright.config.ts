import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./rbac-tests",
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.RBAC_BASE_URL || "http://127.0.0.1:8000",
  },
})
