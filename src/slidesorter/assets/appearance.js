(() => {
  const supported = new Set(["system", "light", "dark"]);
  const systemPreference = window.matchMedia("(prefers-color-scheme: dark)");
  let selected = "system";

  function apply(value) {
    selected = supported.has(value) ? value : "system";
    const appearance = selected === "system"
      ? (systemPreference.matches ? "dark" : "light")
      : selected;
    const root = document.documentElement;
    root.dataset.appearance = appearance;
    root.style.colorScheme = appearance;
  }

  window.SlideSorterAppearance = { apply };
  apply("system");
  systemPreference.addEventListener("change", () => {
    if (selected === "system") apply("system");
  });
  fetch("/api/settings", { cache: "no-store" })
    .then(response => response.ok ? response.json() : Promise.reject(new Error("Appearance unavailable")))
    .then(config => apply(config.appearance))
    .catch(() => apply("system"));
})();
