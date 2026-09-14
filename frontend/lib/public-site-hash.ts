export function scrollToPublicSection(id: string, behavior: ScrollBehavior = "smooth"): boolean {
  const el = document.getElementById(id);
  if (!el) return false;
  el.scrollIntoView({ behavior, block: "start" });
  return true;
}

export function installPublicHashScroll(): () => void {
  const run = () => {
    const id = window.location.hash.replace(/^#/, "");
    if (!id) return;

    let attempts = 0;
    const tick = () => {
      if (scrollToPublicSection(id, attempts === 0 ? "auto" : "smooth")) return;
      attempts += 1;
      if (attempts < 12) window.setTimeout(tick, 100);
    };
    tick();
  };

  run();
  window.addEventListener("hashchange", run);
  return () => window.removeEventListener("hashchange", run);
}
