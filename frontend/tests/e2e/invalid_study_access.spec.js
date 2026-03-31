const { test, expect } = require('@playwright/test');

test('non-existent study shows error message and does not show fallback study content', async ({ page }) => {
  const uid = `pw_invalid_study_${Date.now()}`;
  await page.goto(`http://localhost:3000/rate/study.html?study_name=this_study_does_not_exist&uid=${uid}&lang=en`);

  // Wait until the study coordinator has finished its backend check
  await expect.poll(async () =>
    page.evaluate(() => Boolean(window.study?.backendChecked))
  ).toBeTruthy();

  // The study intro content (songs, dimensions, usage instructions, begin button) must be hidden
  await expect(page.locator('#study-intro-content')).toBeHidden();

  // The blocked-study message must be shown inline on the page
  const blockedMessageEl = page.locator('#study-blocked-message');
  await expect(blockedMessageEl).toBeVisible();
  const blockedText = await blockedMessageEl.textContent();
  expect(blockedText.trim().length).toBeGreaterThan(0);
  // Must contain the real error text (404 message), not the internal default study name/description
  expect(blockedText).toContain('not found');
  expect(blockedText).not.toContain('Default study');

  // Error toast must be present in the user messages container
  const errorMessages = page.locator('#user-messages .error-message');
  await expect(errorMessages.first()).toBeVisible();
  const toastText = await errorMessages.first().textContent();
  expect(toastText).toContain('not found');
});

test('unauthorized study access shows error message and does not show fallback study content', async ({ page }) => {
  // To provoke a 403, we use a known-existing study but a participant id that is not listed in a
  // closed study. The CI/integration setup may not have such a study, so we intercept the network
  // request and return a 403 response ourselves to reliably test the frontend behaviour.
  const uid = `pw_unauthorized_${Date.now()}`;

  await page.route('**/participants/*/studies/closed_study_fixture/config', route => {
    route.fulfill({
      status: 403,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Access denied' }),
    });
  });

  await page.goto(`http://localhost:3000/rate/study.html?study_name=closed_study_fixture&uid=${uid}&lang=en`);

  // Wait until the study coordinator has finished its backend check
  await expect.poll(async () =>
    page.evaluate(() => Boolean(window.study?.backendChecked))
  ).toBeTruthy();

  // The study intro content (songs, dimensions, usage instructions, begin button) must be hidden
  await expect(page.locator('#study-intro-content')).toBeHidden();

  // The blocked-study message must be shown inline on the page
  const blockedMessageEl = page.locator('#study-blocked-message');
  await expect(blockedMessageEl).toBeVisible();
  const blockedText = await blockedMessageEl.textContent();
  expect(blockedText.trim().length).toBeGreaterThan(0);
  expect(blockedText).toContain('Access denied');
  expect(blockedText).not.toContain('Default study');

  // Error toast must be present
  const errorMessages = page.locator('#user-messages .error-message');
  await expect(errorMessages.first()).toBeVisible();
  const toastText = await errorMessages.first().textContent();
  expect(toastText).toContain('Access denied');
});
