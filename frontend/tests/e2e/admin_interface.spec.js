const { test, expect } = require('@playwright/test');

test('admin interface study dashboard and participant management', async ({ page }) => {
  const adminUrl = 'http://localhost:3000/ar_backend/admin';
  const participantMgmtUrl = 'http://localhost:3000/ar_backend/admin/participant-management?study_name_short=default';
  const username = 'audiorating_api_admin';
  const password = 'audiorating_api_admin_password';

  page.on('dialog', dialog => dialog.accept());

  // Set HTTP Basic Auth credentials BEFORE navigating
  await page.context().setHTTPCredentials({
    username: username,
    password: password,
  });

  // Navigate to admin interface
  await page.goto(adminUrl);

  // Verify we're on the admin dashboard
  await expect(page).toHaveTitle(/admin|dashboard/i);

  // ===== VERIFY STUDIES TABLE ON DASHBOARD =====
  await expect(page.locator('#study-title-default')).toBeVisible();
  await expect(page.locator('#study-title-default')).toContainText("Default Study (name_short: 'default')");
  await expect(page.locator('#study-total-songs-default')).toHaveText('2');
  await expect(page.locator('#study-status-default')).toHaveText('Active');

  // ===== SWITCH TO PARTICIPANT MANAGEMENT TAB =====
  await page.locator('#nav-participant-management').click();
  await page.waitForLoadState('networkidle');

  // Verify we're on the participant management page
  await expect(page.locator("h2:has-text('Participant Management')")).toBeVisible();

  // ===== SELECT STUDY FROM DROPDOWN =====
  const studyDropdown = page.locator('#studySelect');
  await expect(studyDropdown).toBeVisible();
  await expect(studyDropdown.locator('option[value="default"]')).toContainText('default - Default Study');
  await studyDropdown.selectOption('default');

  // ===== LOOK FOR LOAD PARTICIPANTS BUTTON =====
  const loadBtn = page.locator('#load-participants-btn');
  await loadBtn.click();
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveURL(/study_name_short=default/);
  if ((await page.locator('#current-participants-section').count()) === 0) {
    await page.goto(participantMgmtUrl);
    await page.waitForLoadState('networkidle');
  }
  await expect(page.locator('#current-participants-section')).toBeVisible();
  await expect(page.locator('#current-participants-title')).toContainText('Participants in "default"');

  // Keep the test idempotent: if participant already exists, remove first.
  const existingRow = page.locator('tr[data-participant-id="bernd_das_brot"]');
  if (await existingRow.count()) {
    await existingRow.locator('button[data-participant-id="bernd_das_brot"]').click();
    await page.waitForLoadState('networkidle');
  }

  // ===== ADD PARTICIPANT =====
  const participantTextarea = page.locator('#participantIds');
  await participantTextarea.fill('bernd_das_brot');

  const addBtn = page.locator('#add-participants-btn');
  await addBtn.click();

  // Wait for the page to update
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1700);
  if ((await page.locator('tr[data-participant-id="bernd_das_brot"]').count()) === 0) {
    await page.goto(participantMgmtUrl);
    await page.waitForLoadState('networkidle');
  }

  // ===== VERIFY PARTICIPANT WAS ADDED =====
  const participantRow = page.locator('tr[data-participant-id="bernd_das_brot"]');
  await expect(participantRow).toBeVisible();
  await expect(page.locator('#current-participants-section')).toContainText('bernd_das_brot');

  // ===== REMOVE PARTICIPANT =====
  const removeBtn = participantRow.locator('button[data-participant-id="bernd_das_brot"]');

  await removeBtn.click();

  // Wait for the page to update
  await page.waitForLoadState('networkidle');

  // ===== VERIFY PARTICIPANT WAS REMOVED =====
  const participantRowAfterRemoval = page.locator('tr[data-participant-id="bernd_das_brot"]');
  await expect(participantRowAfterRemoval).toHaveCount(0);
});
