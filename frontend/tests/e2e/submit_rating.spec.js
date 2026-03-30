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

test('submit rating after editing all dimensions', async ({ page }) => {
  const uid = `pw_submit_rating_${Date.now()}`;
  await page.goto(`http://localhost:3000/rate/study.html?study_name=default&uid=${uid}&lang=en`);

  await expect.poll(async () => page.evaluate(() => {
    const studyReady = Boolean(window.study?.studyConfig?.songs_to_rate?.length);
    const beginButton = document.getElementById('begin-study');
    const totalSongsText = document.getElementById('total-songs')?.textContent?.trim();
    return studyReady && beginButton && !beginButton.disabled && Boolean(totalSongsText);
  })).toBeTruthy();

  await page.locator('#begin-study').click();
  await expect(page.locator('#rating-phase')).toBeVisible();

  const songButtons = page.locator('#song-list .song-nav');
  await expect(songButtons.nth(0)).toHaveClass(/active/);
  await expect(songButtons.nth(0)).toHaveText('1. Demo Song');

  const dimButtons = page.locator('.arw-dimension-buttons button');
  await expect(dimButtons.nth(0)).toHaveAttribute('data-dim', 'valence');
  await expect(dimButtons.nth(0)).toHaveText('Valence');
  await expect(dimButtons.nth(0)).toHaveClass(/active/);

  const submitRatingButton = page.locator('#submit-rating');
  await expect(submitRatingButton).toBeDisabled();
  await expect(submitRatingButton).toHaveText('Save Demo Song to Server — Still to rate: Valence, Arousal, Enjoyment, Is Cool');

  const overlay = page.locator('.arw-overlay');
  await expect(overlay).toBeVisible();

  await splitAtRatio(overlay, 0.33);
  await splitAtRatio(overlay, 0.66);

  const valenceSegments = await page.evaluate(() => window.study.widget.getData().valence.length);
  expect(valenceSegments).toBe(3);

  await dragSegmentToValue(page, overlay, 0.16, 6);
  await dragSegmentToValue(page, overlay, 0.50, 2);
  await dragSegmentToValue(page, overlay, 0.84, 8);

  await expect(submitRatingButton).toHaveText('Save Demo Song to Server — Still to rate: Arousal, Enjoyment, Is Cool');
  await expect(submitRatingButton).toBeDisabled();

  const dimensionsToFinish = ['arousal', 'enjoyment', 'is_cool'];
  for (const dimName of dimensionsToFinish) {
    await page.locator(`.arw-dimension-buttons button[data-dim="${dimName}"]`).click();

    await splitAtRatio(overlay, 0.50);

    const { min, max } = await getLegendRange(page);
    await dragSegmentToValue(page, overlay, 0.25, max);
    await dragSegmentToValue(page, overlay, 0.75, min);
  }

  await expect(submitRatingButton).toBeEnabled();
  await expect(submitRatingButton).toHaveText('Save Demo Song to Server');
});
