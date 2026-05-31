// browser-console JS for extracting GitHub Trending data from SSR HTML
// Run via browser_console(expression=...) after browser_navigate to trending page
// Usage: browser_navigate(url="https://github.com/trending?since=daily")
//        then browser_console(expression=<this script>)

JSON.stringify(Array.from(document.querySelectorAll('article.Box-row')).map(a => {
    const h2 = a.querySelector('h2 a');
    const name = h2 ? h2.getAttribute('href').replace(/^\//, '') : '';
    const desc = a.querySelector('p')?.textContent.trim() || '';
    const lang = a.querySelector('[itemprop="programmingLanguage"]');
    const language = lang ? lang.textContent.trim() : '';
    const starsEl = a.querySelector('a[href*="/stargazers"]');
    const stars = starsEl ? starsEl.textContent.trim().replace(/,/g, '') : '';
    const todayText = Array.from(a.querySelectorAll('*')).find(el =>
        el.textContent.includes('stars today'));
    const m = todayText ? todayText.textContent.match(/([\d,]+)\s+stars?\s+today/) : null;
    return {
        name,
        desc,
        language,
        stars,
        stars_today: m ? m[1].replace(/,/g, '') : ''
    };
}))
