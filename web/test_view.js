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
  check(await page.locator('.sum-lane').count() === 1, 'The centered view must show only the rearranged sum');
  const trailInk = () => page.locator('#sumArcs').evaluate(canvas => {
    const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) count++;
    return count;
  });
  check(await trailInk() === 0, 'A new run must start with an empty trajectory');
  const advance = page.getByRole('button', {name: 'Шаг', exact: true});
  await advance.click();
  const followsArc = await page.locator('#arrangedMarker').evaluate(node =>
    node.getAnimations().some(animation => animation.effect.getKeyframes().some(frame => Number.parseFloat(frame.top) < -1)));
  check(followsArc, 'The marker must move along the arc');
  const firstInk = await trailInk();
  check(firstInk > 0, 'A step must draw a saved arc');
  await advance.click();
  check((await state()).marker > 50, 'The sum must cross to the right of L');
  await advance.click();
  check((await state()).marker < 50, 'The sum must cross back to the left of L');
  check(await trailInk() > firstInk, 'New steps must keep previous arcs');
  const speeds = [];
  for (const speed of ['1x', '5x', '20x']) {
    await page.getByRole('button', {name: 'Сначала', exact: true}).click();
    check(await trailInk() === 0, 'Reset must clear the trajectory');
    await page.getByRole('combobox', {name: 'Скорость'}).selectOption(speed);
    const recording = page.evaluate(() => new Promise(resolve => {
      const counter = document.querySelector('#count'), seen = [Number(counter.textContent)];
      const observer = new MutationObserver(() => {
        const value = Number(counter.textContent);
        if (value !== seen.at(-1)) seen.push(value);
      });
      observer.observe(counter, {childList: true});
      setTimeout(() => { observer.disconnect(); resolve(seen); }, 700);
    }));
    await page.getByRole('button', {name: 'Воспроизвести', exact: true}).click();
    const seen = await recording;
    await page.getByRole('button', {name: 'Пауза', exact: true}).click();
    check(seen.length > 1 && seen.every((value, i) => i === 0 || value === seen[i - 1] + 1), 'Playback must never skip a step at ' + speed);
    speeds.push(seen.at(-1));
  }
  check(speeds[0] < speeds[1] && speeds[1] < speeds[2], 'Higher speed must advance more steps in the same time');
  check(Math.abs((await state()).center - .5) < .002, 'Playback must keep L fixed');
  await page.getByRole('slider', {name: 'Текущий шаг'}).press('End');
  const final = await state();
  check(Math.abs(final.marker - 50) <= final.band / 2, 'The final sum must be inside the tolerance band');
  await page.getByRole('button', {name: 'График', exact: true}).click();
  check(await page.locator('#chart').isVisible(), 'The original graph must remain available');
  await page.getByRole('button', {name: 'К цели L', exact: true}).click();
  check((await state()).count === final.count, 'Changing views must preserve the current step');
  check(await trailInk() > 0, 'Changing views must preserve the trajectory');
  await page.setViewportSize({width: 390, height: 844});
  await page.getByRole('checkbox', {name: 'Вблизи L'}).check();
  const mobile = await state();
  check(!mobile.overflow && Math.abs(mobile.center - .5) < .002, 'The narrow layout must keep L centered without overflow');
  check(await page.locator('#centerStage').evaluate(node => node.clientHeight >= 320), 'The mobile visualization must be enlarged');
  check(await page.locator('#arrangedMarker .point').evaluate(node => node.getBoundingClientRect().width >= 28), 'The current sum must be easy to see');
  check(await trailInk() > 0, 'Resize and zoom must redraw the saved trajectory');
  return {checked: 'Saved arcs, curved motion, reset, sequential playback and narrow layout', stepsPer700ms: speeds};
}
