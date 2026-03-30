const { test, expect } = require('@playwright/test');

async function countTimelineLabels(page) {
  const labels = await page.locator('[part="timeline-notch"]').allTextContents();
  return labels.filter((text) => text.trim().length > 0).length;
}

test('timeline ticks remain visible and get denser after zoom', async ({ page }) => {
  const uid = `pw_timeline_zoom_${Date.now()}`;
  await page.goto(`http://localhost:3000/rate/study.html?study_name=default&uid=${uid}&lang=en`);

  await page.locator('#begin-study').click();
  await expect(page.locator('#rating-phase')).toHaveClass(/active/);

  await page.locator('#song-list .song-nav', { hasText: '2. Demo Song 2' }).click();
  await page.waitForTimeout(600);

  const labelsBefore = await countTimelineLabels(page);
  expect(labelsBefore).toBeGreaterThan(0);

  const zoomInButton = page.locator('.arw-zoom-in');
  let labelsAfter = labelsBefore;
  for (let i = 0; i < 5; i++) {
    await zoomInButton.click();
    await page.waitForTimeout(350);
    labelsAfter = await countTimelineLabels(page);
    if (labelsAfter > labelsBefore) {
      break;
    }
  }

  expect(labelsAfter).toBeGreaterThan(0);
  expect(labelsAfter).toBeGreaterThan(labelsBefore);
});
