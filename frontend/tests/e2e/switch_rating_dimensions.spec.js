const { test, expect } = require('@playwright/test');

test('switch rating dimensions across songs', async ({ page }) => {
  const uid = `pw_switch_dims_${Date.now()}`;
  await page.goto(`http://localhost:3000/rate/study.html?study_name=default&uid=${uid}&lang=en`);

  const beginButton = page.locator('#begin-study');
  await expect(beginButton).toBeVisible();
  await beginButton.click();

  const ratingPhase = page.locator('#rating-phase');
  await expect(ratingPhase).toHaveClass(/active/);

  const songButtons = page.locator('#song-list .song-nav');
  await expect(songButtons).toHaveCount(2);
  await expect(songButtons.nth(0)).toHaveText('1. Demo Song');
  await expect(songButtons.nth(1)).toHaveText('2. Demo Song 2');

  const submitStudyButton = page.locator('#submit-study');
  await expect(submitStudyButton).toBeDisabled();
  await expect(page.locator('#study-completion-status')).toHaveText('0 of 2 songs saved to server');

  const dimButtons = page.locator('.arw-dimension-buttons button');
  await expect(dimButtons.first()).toHaveClass(/active/);
  await expect(dimButtons.first()).toHaveAttribute('data-dim', 'valence');
  await expect(dimButtons.first()).toHaveText('Valence');

  const legendItems = page.locator('.arw-legend .legend-item');
  await expect(legendItems).toHaveCount(8);

  await page.locator('.arw-dimension-buttons button[data-dim="arousal"]').click();
  await expect(legendItems).toHaveCount(5);

  await page.locator('#song-list .song-nav', { hasText: '2. Demo Song 2' }).click();

  await page.locator('.arw-dimension-buttons button[data-dim="enjoyment"]').click();
  await expect(legendItems).toHaveCount(10);

  await page.locator('.arw-dimension-buttons button[data-dim="is_cool"]').click();
  await expect(legendItems).toHaveCount(2);
});
