import { expect, test } from "@playwright/test"

for (const role of ["admin", "manager", "member"] as const) {
  test(`${role}: navigation, direct URLs and user actions`, async ({
    page,
    request,
    baseURL,
  }) => {
    const login = await request.post(`${baseURL}/api/v1/login/access-token`, {
      form: {
        username: `${role}@example.com`,
        password: process.env.RBAC_DEMO_PASSWORD!,
      },
    })
    expect(login.ok()).toBeTruthy()
    const { access_token } = await login.json()
    await page.addInitScript(
      (token) => localStorage.setItem("access_token", token),
      access_token,
    )
    await page.goto("/")
    if (role === "member") {
      await expect(
        page.getByRole("link", { name: "Users", exact: true }),
      ).toHaveCount(0)
      await expect(
        page.getByRole("link", { name: "Metrics", exact: true }),
      ).toHaveCount(0)
      for (const route of ["/admin", "/metrics"]) {
        await page.goto(route)
        await expect(
          page.getByRole("heading", { name: "Access denied", exact: true }),
        ).toBeVisible()
        await expect(page).not.toHaveURL(/login/)
      }
    } else {
      await expect(
        page.getByRole("link", { name: "Users", exact: true }),
      ).toBeVisible()
      await page.goto("/metrics")
      await expect(
        page.getByRole("heading", { name: "Metrics", exact: true }),
      ).toBeVisible()
      await expect(page.getByText(/Registered users:/)).toBeVisible()
      await page.goto("/admin")
      await expect(
        page.getByRole("heading", { name: "Users", exact: true }),
      ).toBeVisible()
      await expect(
        page.getByRole("button", { name: "Add User", exact: true }),
      ).toHaveCount(role === "admin" ? 1 : 0)
      if (role === "manager")
        await expect(page.getByText("Edit User", { exact: true })).toHaveCount(
          0,
        )
    }
    if (role === "admin") {
      const email = `ui-created-${Date.now()}@example.com`
      await page.getByRole("button", { name: "Add User", exact: true }).click()
      await page.getByPlaceholder("Email", { exact: true }).fill(email)
      await page
        .getByPlaceholder("Full name", { exact: true })
        .fill("UI-created manager")
      await page
        .getByPlaceholder("Password", { exact: true })
        .first()
        .fill("Browser-review-Password-123!")
      await page
        .getByPlaceholder("Password", { exact: true })
        .last()
        .fill("Browser-review-Password-123!")
      await page.getByLabel("Role", { exact: true }).selectOption("manager")
      await page.getByLabel("Is active?", { exact: true }).check()
      await page.getByRole("button", { name: "Save", exact: true }).click()
      await expect(
        page.getByText("User created successfully", { exact: true }),
      ).toBeVisible()
      const row = page.getByRole("row").filter({ hasText: email })
      await expect(row.getByText("manager", { exact: true })).toBeVisible()
      await row.getByRole("button").click()
      await page.getByRole("menuitem", { name: "Edit User" }).click()
      await page
        .getByPlaceholder("Full name", { exact: true })
        .fill("UI-updated manager")
      await page.getByRole("button", { name: "Save", exact: true }).click()
      await expect(
        row.getByText("UI-updated manager", { exact: true }),
      ).toBeVisible()
      await row.getByRole("button").click()
      await page.getByRole("menuitem", { name: "Delete User" }).click()
      await page.getByRole("button", { name: "Delete", exact: true }).click()
      await expect(row).toHaveCount(0)
    }
    await page.screenshot({
      path: `../.evidence/${role}-ui.png`,
      fullPage: true,
    })
  })
}
