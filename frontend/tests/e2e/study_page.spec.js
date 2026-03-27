const { test, expect } = require('@playwright/test');

test('study page loads and has begin-study button', async ({ page }) => {
  await page.goto('http://localhost:3000/rate/study.html?lang=en');

  await expect(page).toHaveTitle(/Audio Rating Study/);

  const beginButton = page.locator('#begin-study');
  await expect(beginButton).toBeVisible();
});
