// // static/js/index.js
// document.addEventListener('DOMContentLoaded', () => {
//   const feed = document.querySelector('.juicer-feed');
//   const expandBtn = document.getElementById('expand-btn');

//   if (!feed) {
//     console.warn('Juicer feed container (.juicer-feed) not found — skipping feed init.');
//     return;
//   }

//   let visibleItems = 0;
//   let expandCount = 0;

//   function initFeedItems() {
//     try {
//       const items = Array.from(feed.children).filter(n => n.nodeType === 1);
//       if (!items.length) return false;

//       // Reset classes (safe)
//       feed.classList.add('row-1');
//       items.forEach(el => el.classList.remove('visible'));

//       visibleItems = Math.min(4, items.length); // show first row (4 items)
//       items.slice(0, visibleItems).forEach(item => item.classList.add('visible'));

//       if (expandBtn) expandBtn.style.display = items.length > visibleItems ? 'block' : 'none';
//       return true;
//     } catch (err) {
//       console.error('Error while initializing Juicer feed items:', err);
//       return false;
//     }
//   }

//   // Use MutationObserver to detect when Juicer injects nodes
//   const observer = new MutationObserver((mutations, obs) => {
//     if (initFeedItems()) obs.disconnect();
//   });
//   observer.observe(feed, { childList: true, subtree: true });

//   // Fallback poll (in case MutationObserver misses something). Stops after ~10s.
//   let polls = 0;
//   const poller = setInterval(() => {
//     polls++;
//     if (initFeedItems() || polls > 20) {
//       clearInterval(poller);
//       if (polls > 20) console.warn('Juicer feed did not populate within expected time.');
//     }
//   }, 500);

//   // Expand button behaviour (guard existence)
//   if (expandBtn) {
//     expandBtn.addEventListener('click', () => {
//       try {
//         const items = Array.from(feed.children).filter(n => n.nodeType === 1);
//         expandCount++;
//         let newVisibleItems;
//         if (expandCount === 1) newVisibleItems = Math.min(12, items.length);
//         else newVisibleItems = items.length;

//         items.slice(visibleItems, newVisibleItems).forEach(item => item.classList.add('visible'));
//         visibleItems = newVisibleItems;

//         if (visibleItems >= items.length) expandBtn.style.display = 'none';
//       } catch (err) {
//         console.error('Error while expanding Juicer feed:', err);
//       }
//     });
//   }
// });

document.addEventListener('DOMContentLoaded', () => {
  const feed = document.querySelector('.juicer-feed');
  const expandBtn = document.getElementById('expand-btn');
  let visibleItems = 0;
  let expandCount = 0;

  const checkFeed = setInterval(() => {
    if (feed && feed.children.length > 0) {
      clearInterval(checkFeed);
      const items = Array.from(feed.children);
      visibleItems = Math.min(4, items.length);
      feed.classList.add('row-1');
      items.slice(0, visibleItems).forEach(item => item.classList.add('visible'));
      expandBtn.style.display = items.length > visibleItems ? 'block' : 'none';
    }
  }, 500);

  expandBtn.addEventListener('click', () => {
    expandCount++;
    const items = Array.from(feed.children);
    let newVisibleItems;

    if (expandCount === 1) {
      newVisibleItems = Math.min(12, items.length);
    } else {
      newVisibleItems = items.length;
    }

    items.slice(visibleItems, newVisibleItems).forEach(item => item.classList.add('visible'));
    visibleItems = newVisibleItems;

    if (visibleItems >= items.length) {
      expandBtn.style.display = 'none';
    }
  });
});
