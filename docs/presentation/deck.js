// ReviewRadar · Checkpoint 2 deck: scaling, navigation, fullscreen.
(function () {
  const W = 1920, H = 1080;
  const stage = document.getElementById("stage");
  const slides = Array.from(stage.querySelectorAll(".slide"));
  const counter = document.getElementById("counter");
  const chapter = document.getElementById("chapter");
  const bar = document.getElementById("bar");
  const pad = (n) => String(n).padStart(2, "0");
  let current = -1;

  function fit() {
    const s = Math.min(window.innerWidth / W, window.innerHeight / H);
    stage.style.transform = `scale(${s}) translate(-50%, -50%)`;
  }

  function go(n) {
    n = Math.max(0, Math.min(slides.length - 1, n));
    if (n === current) return;
    slides.forEach((el, i) => {
      el.classList.toggle("is-active", i === n);
      el.classList.toggle("is-before", i < n);
      el.setAttribute("aria-hidden", i === n ? "false" : "true");
    });
    current = n;
    stage.dataset.current = n;
    counter.innerHTML = `<b>${pad(n + 1)}</b> / ${pad(slides.length)}`;
    chapter.textContent = n === 0 ? "" : slides[n].dataset.label;
    bar.style.width = `${((n + 1) / slides.length) * 100}%`;
    if (location.hash !== `#${n + 1}`) history.replaceState(null, "", `#${n + 1}`);
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen?.().catch(() => {});
  }

  document.addEventListener("keydown", (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    switch (e.key) {
      case "ArrowRight": case "ArrowDown": case "PageDown": case "Enter":
        e.preventDefault(); go(current + 1); break;
      case " ":
        e.preventDefault(); go(current + (e.shiftKey ? -1 : 1)); break;
      case "ArrowLeft": case "ArrowUp": case "PageUp": case "Backspace":
        e.preventDefault(); go(current - 1); break;
      case "Home": e.preventDefault(); go(0); break;
      case "End": e.preventDefault(); go(slides.length - 1); break;
      case "f": case "F": e.preventDefault(); toggleFullscreen(); break;
    }
  });

  document.getElementById("prev").addEventListener("click", () => go(current - 1));
  document.getElementById("next").addEventListener("click", () => go(current + 1));
  document.getElementById("fs").addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", () => {
    document.body.classList.toggle("is-fullscreen", !!document.fullscreenElement);
    fit();
  });

  // Touch swipe
  let x0 = null;
  stage.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  stage.addEventListener("touchend", (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 50) go(current + (dx < 0 ? 1 : -1));
    x0 = null;
  });

  // Show controls briefly when the pointer moves
  let idle;
  document.addEventListener("mousemove", () => {
    document.body.classList.add("show-controls");
    clearTimeout(idle);
    idle = setTimeout(() => document.body.classList.remove("show-controls"), 1800);
  });

  window.addEventListener("resize", fit);
  window.addEventListener("hashchange", () => go(parseInt(location.hash.slice(1), 10) - 1 || 0));

  fit();
  go((parseInt(location.hash.slice(1), 10) || 1) - 1);
})();
