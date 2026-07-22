const revealTargets = document.querySelectorAll(".problem-grid article, .feature-card, .workflow li, .summary-card, .chat");

if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  for (const element of revealTargets) element.classList.add("reveal-pending");
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add("reveal-visible");
      observer.unobserve(entry.target);
    }
  }, { threshold: 0.12 });
  for (const element of revealTargets) observer.observe(element);
}
