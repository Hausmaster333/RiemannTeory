// Playwright CLI: open the site, then run-code with the contents of this file.
async (page) => {
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  await page.goto(new URL('?view=center', page.url()).href);
  const state = () => page.evaluate(() => {
    const plot = document.querySelector('.center-plot').getBoundingClientRect();
    const target = document.querySelector('.target-guide').getBoundingClientRect();
    return {
      center: (target.left - plot.left) / plot.width,
      marker: Number.parseFloat(document.querySelector('#arrangedMarker').style.left),
      band: Number.parseFloat(document.querySelector('#toleranceBand').style.width),
      count: document.querySelector('#count').textContent,
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth
    };
  });
  check(Math.abs((await state()).center - .5) < .002, 'L must be fixed at the center');
  const advance = page.getByRole('button', {name: 'Шаг', exact: true});
  await advance.click();
  await advance.click();
  check((await state()).marker > 50, 'The sum must cross to the right of L');
  await advance.click();
  check((await state()).marker < 50, 'The sum must cross back to the left of L');
  await page.getByRole('button', {name: 'Сначала', exact: true}).click();
  await page.getByRole('combobox', {name: 'Скорость'}).selectOption('1x');
  await page.getByRole('button', {name: 'Воспроизвести', exact: true}).click();
  await page.waitForFunction(() => Number(document.querySelector('#count').textContent) >= 2);
  await page.getByRole('button', {name: 'Пауза', exact: true}).click();
  check(Math.abs((await state()).center - .5) < .002, 'Playback must keep L fixed');
  await page.getByRole('slider', {name: 'Текущий шаг'}).press('End');
  const final = await state();
  check(Math.abs(final.marker - 50) <= final.band / 2, 'The final sum must be inside the tolerance band');
  await page.getByRole('button', {name: 'График', exact: true}).click();
  check(await page.locator('#chart').isVisible(), 'The original graph must remain available');
  await page.getByRole('button', {name: 'К цели L', exact: true}).click();
  check((await state()).count === final.count, 'Changing views must preserve the current step');
  await page.setViewportSize({width: 390, height: 844});
  const mobile = await state();
  check(!mobile.overflow && Math.abs(mobile.center - .5) < .002, 'The narrow layout must keep L centered without overflow');
  return {checked: 'Center, crossings, tolerance, view switching and narrow layout'};
}
