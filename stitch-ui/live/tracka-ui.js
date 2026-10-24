/* Shared, API-independent UI wiring for Track A static pages. */
(function () {
  "use strict";
  const header = document.querySelector("header");
  const workspace = document.querySelector(".rift-tracka-workspace");
  const aside = document.querySelector("body > aside");
  if (!header || !workspace || !aside) return;

  function toast(message) {
    let el = document.getElementById("rift-tracka-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "rift-tracka-toast";
      el.setAttribute("role", "status");
      el.setAttribute("aria-live", "polite");
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.style.display = "block";
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(() => { el.style.display = "none"; }, 3600);
  }

  const toolbar = header.querySelector(":scope > div");
  if (toolbar && !document.getElementById("rift-nav-toggle")) {
    const navToggle = document.createElement("button");
    navToggle.id = "rift-nav-toggle";
    navToggle.type = "button";
    navToggle.setAttribute("aria-label", "Toggle navigation");
    navToggle.setAttribute("aria-expanded", "false");
    navToggle.innerHTML = '<span class="material-symbols-outlined" aria-hidden="true">menu</span>';
    toolbar.insertBefore(navToggle, toolbar.firstChild);

    const scrim = document.createElement("div");
    scrim.id = "rift-scrim";
    scrim.setAttribute("aria-hidden", "true");
    document.body.appendChild(scrim);

    function mobile() { return window.matchMedia("(max-width: 767px)").matches; }
    function closeMobileNav() {
      document.body.classList.remove("rift-nav-open");
      navToggle.setAttribute("aria-expanded", "false");
    }
    navToggle.addEventListener("click", function () {
      if (mobile()) {
        const open = document.body.classList.toggle("rift-nav-open");
        navToggle.setAttribute("aria-expanded", String(open));
      } else {
        const collapsed = document.body.classList.toggle("rift-nav-collapsed");
        navToggle.setAttribute("aria-expanded", String(!collapsed));
        try { localStorage.setItem("rift-nav", collapsed ? "collapsed" : "open"); } catch (_) {}
      }
    });
    scrim.addEventListener("click", closeMobileNav);
    aside.querySelectorAll("a").forEach(a => a.addEventListener("click", closeMobileNav));
    window.addEventListener("resize", function () {
      if (!mobile()) closeMobileNav();
      else document.body.classList.remove("rift-nav-collapsed");
    });
    try {
      if (localStorage.getItem("rift-nav") === "collapsed" && !mobile()) {
        document.body.classList.add("rift-nav-collapsed");
        navToggle.setAttribute("aria-expanded", "false");
      }
    } catch (_) {}
  }

  // Header controls use honest, useful actions and never pretend to deploy a service.
  header.querySelectorAll("button").forEach(function (button) {
    if (button.id === "rift-nav-toggle" || button.id === "rift-avatar" || button.dataset.trackaWired === "true") return;
    const label = (button.textContent || "").trim();
    const glyph = button.querySelector(".material-symbols-outlined")?.textContent.trim() || "";
    if (/^verify snapshot/i.test(label)) {
      button.dataset.trackaWired = "true";
      button.addEventListener("click", function () {
        toast("Refreshing the Track A page and its committed evaluation data…");
        window.setTimeout(() => window.location.reload(), 350);
      });
    } else if (/^deploy override/i.test(label)) {
      button.dataset.trackaWired = "true";
      button.addEventListener("click", function () {
        toast("No deployment action is available here. Use the Render service dashboard to deploy.");
      });
    } else if (glyph === "notifications_active" || /alert/i.test(label)) {
      button.dataset.trackaWired = "true";
      button.addEventListener("click", () => { window.location.href = "./runs.html"; });
    } else if (glyph === "help_outline") {
      button.dataset.trackaWired = "true";
      button.addEventListener("click", () => { window.location.href = "./explainability.html"; });
    } else if (glyph === "tune") {
      button.dataset.trackaWired = "true";
      button.addEventListener("click", () => { window.location.href = "./settings.html"; });
    }
  });

  const actionGroup = header.querySelector(".flex.items-center.gap-2");
  if (actionGroup && !document.getElementById("rift-avatar")) {
    const avatar = document.createElement("button");
    avatar.id = "rift-avatar";
    avatar.type = "button";
    avatar.setAttribute("aria-label", "Account menu");
    avatar.setAttribute("aria-expanded", "false");
    avatar.style.cssText = "width:34px;height:34px;flex:0 0 34px;border-radius:50%;border:1px solid #0891b2;background:#0f172a;color:#67e8f9;font-size:12px;font-weight:700;margin-left:6px;cursor:pointer;";
    avatar.textContent = "R";
    actionGroup.appendChild(avatar);

    const menu = document.createElement("div");
    menu.id = "rift-tracka-account-menu";
    menu.innerHTML =
      '<a href="./dashboard.html">RIFT dashboard</a>' +
      '<a href="./coronary.html">Coronary 3D</a>' +
      '<a href="./cardio-dashboard.html">Cardio Eval</a>' +
      '<a href="./settings.html">Settings</a>';
    document.body.appendChild(menu);
    function hideMenu() {
      menu.style.display = "none";
      avatar.setAttribute("aria-expanded", "false");
    }
    avatar.addEventListener("click", function (event) {
      event.stopPropagation();
      const showing = menu.style.display === "block";
      if (showing) return hideMenu();
      const rect = avatar.getBoundingClientRect();
      menu.style.top = Math.max(8, Math.min(window.innerHeight - 220, rect.bottom + 8)) + "px";
      menu.style.left = Math.max(8, Math.min(window.innerWidth - 226, rect.right - 210)) + "px";
      menu.style.display = "block";
      avatar.setAttribute("aria-expanded", "true");
    });
    menu.addEventListener("click", event => { if (event.target.closest("a")) hideMenu(); });
    document.addEventListener("click", event => {
      if (menu.style.display === "block" && !menu.contains(event.target) && event.target !== avatar) hideMenu();
    });
    document.addEventListener("keydown", event => { if (event.key === "Escape") hideMenu(); });
  }
})();
