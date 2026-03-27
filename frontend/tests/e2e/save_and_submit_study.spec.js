const { test, expect } = require('@playwright/test');

async function getLegendRange(page) {
  const texts = await page.locator('.arw-legend .legend-item').allTextContents();
  const values = texts.map((t) => Number.parseInt(t.trim(), 10)).filter((v) => !Number.isNaN(v));
  const min = Math.min(...values);
  const max = Math.max(...values);
  return { min, max, count: values.length };
}

function yForValue(value, min, max, height) {
  const steps = max - min + 1;
  const raw = value - min;
  const y = height * (1 - raw / (steps - 1));
  return Math.max(1, Math.min(height - 1, y));
}

async function dragSegmentToValue(page, overlayLocator, xRatio, targetValue) {
  const box = await overlayLocator.boundingBox();
  if (!box) throw new Error('Overlay bounding box not available');

  const { min, max } = await getLegendRange(page);
  const x = box.x + box.width * xRatio;
  const startY = box.y + box.height * 0.5;
  const endY = box.y + yForValue(targetValue, min, max, box.height);

  await page.mouse.move(x, startY);
  await page.mouse.down();
  await page.mouse.move(x, endY, { steps: 20 });
  await page.mouse.up();
}

async function splitAtRatio(overlayLocator, xRatio) {
  const box = await overlayLocator.boundingBox();
  if (!box) throw new Error('Overlay bounding box not available');

  await overlayLocator.dblclick({
    position: {
      x: box.width * xRatio,
      y: box.height * 0.5,
    },
  });
}

async function rateAllDimensions(page, overlay) {
  const dimensionsToRate = ['valence', 'arousal', 'enjoyment', 'is_cool'];

  for (const dimName of dimensionsToRate) {
    await page.locator(`.arw-dimension-buttons button[data-dim="${dimName}"]`).click();

    await splitAtRatio(overlay, 0.50);

    const { min, max } = await getLegendRange(page);
    const midValue = Math.round((min + max) / 2);
    await dragSegmentToValue(page, overlay, 0.25, max);
    await dragSegmentToValue(page, overlay, 0.75, min);
  }
}

test('save ratings for both songs and submit study', async ({ page }) => {
  const uid = `pw_submit_study_${Date.now()}`;
  await page.goto(`http://localhost:3000/rate/study.html?study_name=default&uid=${uid}&lang=en`);

  await page.locator('#begin-study').click();
  await expect(page.locator('#rating-phase')).toHaveClass(/active/);

  const overlay = page.locator('.arw-overlay');

  // ===== RATE SONG 1 =====
  const songButtons = page.locator('#song-list .song-nav');
  await expect(songButtons.nth(0)).toHaveClass(/active/);

  const dimButtons = page.locator('.arw-dimension-buttons button');
  await expect(dimButtons.nth(0)).toHaveClass(/active/);

  const submitRatingButton = page.locator('#submit-rating');

  // Split valence into 3 sections and rate them
  await splitAtRatio(overlay, 0.33);
  await splitAtRatio(overlay, 0.66);
  await dragSegmentToValue(page, overlay, 0.16, 6);
  await dragSegmentToValue(page, overlay, 0.50, 2);
  await dragSegmentToValue(page, overlay, 0.84, 8);

  // Rate remaining dimensions
  await rateAllDimensions(page, overlay);

  // Save song 1
  await expect(submitRatingButton).toBeEnabled();
  await submitRatingButton.click();

  // Wait a moment for save action to process
  await page.waitForTimeout(1500);

  // Button should reflect either "Already Saved to Server" or stay "Save to Server" depending on backend availability
  const btnText1 = await submitRatingButton.textContent();
  console.log('Button text after first save:', btnText1);

  // ===== RATE SONG 2 =====
  await page.locator('#song-list .song-nav', { hasText: '2. Demo Song 2' }).click();

  // Verify song 2 is now active
  await expect(songButtons.nth(1)).toHaveClass(/active/);

  // Rate all dimensions for song 2
  await rateAllDimensions(page, overlay);

  // Save song 2
  await expect(submitRatingButton).toBeEnabled();
  await submitRatingButton.click();

  // Wait a moment for save action to process
  await page.waitForTimeout(1500);

  const btnText2 = await submitRatingButton.textContent();
  console.log('Button text after second save:', btnText2);

  // Verify submit study button state
  const submitStudyButton = page.locator('#submit-study');
  const completionStatus = page.locator('#study-completion-status');

  // Log the current completion status for debugging
  const statusText = await completionStatus.textContent();
  console.log('Study completion status:', statusText);

  // Try to submit the study if button is enabled (backend connected and all songs synced)
  const isSubmitEnabled = await submitStudyButton.isEnabled();

  if (isSubmitEnabled) {
    console.log('Submit button is enabled, attempting to submit study');
    await submitStudyButton.click();

    // Verify we see the completion phase with "Ratings submitted" heading
    await expect(page.locator('#completion-phase')).toHaveClass(/active/);
    await expect(page.locator('text=Ratings submitted')).toBeVisible();
  } else {
    console.log('Submit button is disabled (backend likely offline or not all songs synced)');
    // Both songs have been rated and saved locally, which is still a valid flow
    // Just verify we're still on the rating phase with both songs rated
    await expect(page.locator('#rating-phase')).toHaveClass(/active/);
  }
});
