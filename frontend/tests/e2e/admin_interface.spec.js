const { test, expect } = require('@playwright/test');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

function formatUtcDate(date) {
  return date.toISOString().slice(0, 10);
}

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
  await expect(page.locator('#study-status-default')).toContainText('Collection:');

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


test('admin runtime config download buttons export JSON', async ({ page }) => {
  const adminUrl = 'http://localhost:3000/ar_backend/admin';
  const username = 'audiorating_api_admin';
  const password = 'audiorating_api_admin_password';

  await page.context().setHTTPCredentials({
    username,
    password,
  });

  await page.goto(adminUrl);
  await expect(page.locator('#download-runtime-config-default')).toBeVisible();
  await expect(page.locator('#download-runtime-config-all')).toBeVisible();

  const singleStudyDownloadPromise = page.waitForEvent('download');
  await page.locator('#download-runtime-config-default').click();
  const singleStudyDownload = await singleStudyDownloadPromise;

  expect(singleStudyDownload.suggestedFilename()).toMatch(/studies_runtime_config_default_.*\.json$/);

  const singleStudyFile = path.join(os.tmpdir(), singleStudyDownload.suggestedFilename());
  await singleStudyDownload.saveAs(singleStudyFile);
  const singleStudyContent = JSON.parse(await fs.readFile(singleStudyFile, 'utf8'));

  expect(singleStudyContent).toHaveProperty('studies_config');
  expect(singleStudyContent).toHaveProperty('logged_ratings');
  expect(singleStudyContent.studies_config.studies).toHaveLength(1);
  expect(singleStudyContent.studies_config.studies[0].name_short).toBe('default');
  expect(singleStudyContent.logged_ratings).toHaveProperty('default');

  const allStudiesDownloadPromise = page.waitForEvent('download');
  await page.locator('#download-runtime-config-all').click();
  const allStudiesDownload = await allStudiesDownloadPromise;

  expect(allStudiesDownload.suggestedFilename()).toMatch(/studies_runtime_config_.*\.json$/);

  const allStudiesFile = path.join(os.tmpdir(), allStudiesDownload.suggestedFilename());
  await allStudiesDownload.saveAs(allStudiesFile);
  const allStudiesContent = JSON.parse(await fs.readFile(allStudiesFile, 'utf8'));

  expect(allStudiesContent).toHaveProperty('studies_config');
  expect(allStudiesContent).toHaveProperty('logged_ratings');
  expect(Array.isArray(allStudiesContent.studies_config.studies)).toBeTruthy();
  expect(allStudiesContent.studies_config.studies.length).toBeGreaterThan(0);

  const studyNames = allStudiesContent.studies_config.studies.map((study) => study.name_short);
  expect(studyNames).toContain('default');
});


test('admin dashboard collection window controls update active state and visible dates', async ({ page }) => {
  const adminUrl = 'http://localhost:3000/ar_backend/admin';
  const username = 'audiorating_api_admin';
  const password = 'audiorating_api_admin_password';

  await page.context().setHTTPCredentials({ username, password });
  await page.goto(adminUrl);

  const studyShortName = 'default';
  const studyCard = page.locator(`#study-card-${studyShortName}`);
  const now = new Date();
  const yesterday = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - 1));
  const twoDaysAgo = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - 2));
  const tomorrow = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1));

  const pausedStartDate = formatUtcDate(twoDaysAgo);
  const pausedEndDate = formatUtcDate(yesterday);
  const activeStartDate = formatUtcDate(yesterday);
  const activeEndDate = formatUtcDate(tomorrow);

  const startInput = studyCard.locator('[id^="window-start-"]');
  const endInput = studyCard.locator('[id^="window-end-"]');
  const saveWindowButton = studyCard.getByRole('button', { name: 'Save Window' });
  const pauseButton = studyCard.locator('#pause-study-btn-default');
  const studyStatus = studyCard.locator('#study-status-default');
  const collectionState = studyCard.locator('#collection-state-default');
  const studyStartLabel = studyCard.locator('#study-start-default');
  const studyEndLabel = studyCard.locator('#study-end-default');
  const windowStatus = studyCard.locator('[id^="window-status-"]');

  await startInput.fill(activeStartDate);
  await endInput.fill(activeEndDate);
  await saveWindowButton.click();

  await expect(windowStatus).toHaveText('Collection window updated.');
  await expect(studyStatus).toHaveText('Collection: Active');
  await expect(collectionState).toHaveText('Active');
  const updatedActiveStartDate = await startInput.inputValue();
  const updatedActiveEndDate = await endInput.inputValue();
  await expect(studyStartLabel).toHaveText(updatedActiveStartDate);
  await expect(studyEndLabel).toHaveText(updatedActiveEndDate);
  await expect(pauseButton).toBeEnabled();

  await pauseButton.click();
  await expect(windowStatus).toHaveText('Collection window updated.');
  await expect(studyStatus).toHaveText('Collection: Inactive');
  await expect(collectionState).toHaveText('Inactive');
  const updatedPausedStartDate = await startInput.inputValue();
  const updatedPausedEndDate = await endInput.inputValue();
  await expect(studyStartLabel).toHaveText(updatedPausedStartDate);
  await expect(studyEndLabel).toHaveText(updatedPausedEndDate);
  await expect(pauseButton).toBeDisabled();

  await startInput.fill(activeStartDate);
  await endInput.fill(activeEndDate);
  await saveWindowButton.click();

  await expect(windowStatus).toHaveText('Collection window updated.');
  await expect(studyStatus).toHaveText('Collection: Active');
  await expect(collectionState).toHaveText('Active');
  const reactivatedStartDate = await startInput.inputValue();
  const reactivatedEndDate = await endInput.inputValue();
  await expect(studyStartLabel).toHaveText(reactivatedStartDate);
  await expect(studyEndLabel).toHaveText(reactivatedEndDate);
  await expect(pauseButton).toBeEnabled();
});


test('admin participant management can switch study from open to closed and back', async ({ page }) => {
  const participantMgmtUrl = 'http://localhost:3000/ar_backend/admin/participant-management?study_name_short=default';
  const username = 'audiorating_api_admin';
  const password = 'audiorating_api_admin_password';

  page.on('dialog', dialog => dialog.accept());

  await page.context().setHTTPCredentials({ username, password });
  await page.goto(participantMgmtUrl);

  const studyTypeBadge = page.locator('#study-type-badge');
  const toggleStudyTypeButton = page.locator('#toggle-study-type-btn');

  const initialIsOpen = (await toggleStudyTypeButton.getAttribute('data-is-open')) === 'true';

  if (!initialIsOpen) {
    await toggleStudyTypeButton.click();
    await expect(studyTypeBadge).toHaveText('Open Study');
    await expect(toggleStudyTypeButton).toHaveText('Switch to Closed');
    await expect(toggleStudyTypeButton).toHaveAttribute('data-is-open', 'true');
  }

  await toggleStudyTypeButton.click();
  await expect(studyTypeBadge).toHaveText('Closed Study');
  await expect(toggleStudyTypeButton).toHaveText('Switch to Open');
  await expect(toggleStudyTypeButton).toHaveAttribute('data-is-open', 'false');

  await toggleStudyTypeButton.click();
  await expect(studyTypeBadge).toHaveText('Open Study');
  await expect(toggleStudyTypeButton).toHaveText('Switch to Closed');
  await expect(toggleStudyTypeButton).toHaveAttribute('data-is-open', 'true');
});
