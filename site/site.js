const copyButton = document.querySelector(".copy-button");

copyButton?.addEventListener("click", async () => {
  const command = copyButton.dataset.copy;
  if (!command) return;
  try {
    await navigator.clipboard.writeText(command);
    copyButton.textContent = "Copied";
  } catch {
    copyButton.textContent = "Copy failed";
  }
  window.setTimeout(() => { copyButton.textContent = "Copy"; }, 1800);
});

const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) entry.target.classList.add("is-visible");
  });
}, { threshold: 0.12 });

document.querySelectorAll(".reveal, .workflow-steps li, .fit-list article").forEach(item => observer.observe(item));
