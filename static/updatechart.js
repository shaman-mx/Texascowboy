// static/js/updatechart.js
// Replaces button-driven logic: selects auto-refresh both charts.
// Requires window.refreshFourKindChart and window.refreshAaChart to be defined (returning Promise).

(function () {
  const FK_SELECT_ID = 'fk-agg-select';
  const AA_SELECT_ID = 'aa-agg-select';

  function $(id) { return document.getElementById(id); }

  function parseAgg(el) {
    if (!el) return 1;
    const v = parseInt(el.value, 10);
    return Number.isFinite(v) && v > 0 ? v : 1;
  }

  function setControlsDisabled(disabled) {
    const fk = $(FK_SELECT_ID);
    const aa = $(AA_SELECT_ID);
    if (fk) fk.disabled = disabled;
    if (aa) aa.disabled = disabled;
  }

  // debounce helper
  function debounce(fn, wait) {
    let t = null;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  async function refreshBoth(agg) {
    const tasks = [];
    if (typeof window.refreshFourKindChart === 'function') {
      try { tasks.push(Promise.resolve(window.refreshFourKindChart(agg))); } catch (e) { tasks.push(Promise.reject(e)); }
    }
    if (typeof window.refreshAaChart === 'function') {
      try { tasks.push(Promise.resolve(window.refreshAaChart(agg))); } catch (e) { tasks.push(Promise.reject(e)); }
    }
    if (!tasks.length) return;
    await Promise.all(tasks);
  }

  // Called when user changes either select
  const onSelectChange = debounce(async function (sourceId) {
    const fk = $(FK_SELECT_ID);
    const aa = $(AA_SELECT_ID);
    const source = $(sourceId);
    if (!source) return;

    const agg = parseAgg(source);

    // sync selects
    if (fk && aa) {
      fk.value = String(agg);
      aa.value = String(agg);
    } else if (fk) {
      fk.value = String(agg);
    } else if (aa) {
      aa.value = String(agg);
    }

    // disable selects while loading to avoid concurrent calls
    setControlsDisabled(true);
    try {
      await refreshBoth(agg);
    } catch (err) {
      // keep error visible in console; UI fallback handled by chart modules
      console.error('Error refreshing charts:', err);
    } finally {
      setControlsDisabled(false);
    }
  }, 250);

  // Public trigger (optional) to programmatically refresh charts
  window.triggerChartsRefresh = function (agg) {
    const fk = $(FK_SELECT_ID);
    const aa = $(AA_SELECT_ID);
    if (fk) fk.value = String(agg);
    if (aa) aa.value = String(agg);
    return refreshBoth(agg);
  };

  // Wire up events on DOM ready
  document.addEventListener('DOMContentLoaded', function () {
    const fk = $(FK_SELECT_ID);
    const aa = $(AA_SELECT_ID);

    if (fk) fk.addEventListener('change', () => onSelectChange(FK_SELECT_ID));
    if (aa) aa.addEventListener('change', () => onSelectChange(AA_SELECT_ID));

    // Initial load: prefer FK select value, fallback to AA, default 1
    const initialAgg = parseAgg(fk || aa);
    // run initial refresh but don't block DOMContentLoaded
    (async function () {
      setControlsDisabled(true);
      try {
        await refreshBoth(initialAgg);
      } catch (err) {
        console.error('Initial chart load error:', err);
      } finally {
        setControlsDisabled(false);
      }
    })();
  });
})();