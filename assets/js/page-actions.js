document.addEventListener("DOMContentLoaded", () => {
  const bar = document.querySelector(".page-actions");
  const btn = document.getElementById("copy-page-btn");
  if (!bar || !btn) return;

  btn.addEventListener("click", async () => {
    const label = btn.querySelector("span");
    const original = label.textContent;
    try {
      const res = await fetch(bar.dataset.rawUrl);
      if (!res.ok) throw new Error(res.status);
      await navigator.clipboard.writeText(await res.text());
      label.textContent = "Copied!";
    } catch {
      label.textContent = "Copy failed";
    }
    setTimeout(() => { label.textContent = original; }, 2000);
  });
});
