/* KBN5 Final Frontend Integration */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const modules = [
    ["KBN5CartUI", "Cart"],
    ["KBN5NotificationsUI", "Notifications"],
    ["KBN5AdminUI", "Admin"],
    ["KBN5OperationsUI", "Operations"]
  ];

  function setConnectionStatus(message, state = "ready") {
    const element = $("kbn5-global-status");
    if (!element) return;

    element.textContent = message;
    element.dataset.state = state;
  }

  function safelyRun(label, callback) {
    if (typeof callback !== "function") return;

    try {
      const result = callback();

      if (result && typeof result.catch === "function") {
        result.catch((error) => {
          console.error(`KBN5 ${label}:`, error);
        });
      }
    } catch (error) {
      console.error(`KBN5 ${label}:`, error);
    }
  }

  function initializeNavigation() {
    const menuButton = $("kbn5-menu-toggle");
    const menu = $("kbn5-mobile-menu");

    if (menuButton && menu) {
      menuButton.addEventListener("click", () => {
        const isOpen = menu.classList.toggle("is-open");
        menuButton.setAttribute("aria-expanded", String(isOpen));
      });
    }

    document.querySelectorAll("[data-kbn5-scroll]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = $(button.dataset.kbn5Scroll);
        if (target) {
          target.scrollIntoView({
            behavior: "smooth",
            block: "start"
          });
        }
      });
    });
  }

  function initializeModules() {
    modules.forEach(([globalName, label]) => {
      const module = window[globalName];

      if (!module) {
        console.info(`KBN5 ${label} module is not loaded.`);
        return;
      }

      console.info(`KBN5 ${label} module detected.`);
    });
  }

  function initializeApp() {
    initializeNavigation();
    initializeModules();
    setConnectionStatus("KBN5 storefront ready", "ready");
  }

  window.KBN5Frontend = {
    initialize: initializeApp,
    setConnectionStatus,
    safelyRun
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeApp, {
      once: true
    });
  } else {
    initializeApp();
  }
})();

/* Connect navigation to existing frontend modules */
function initializeQuickActions() {
  const cartButton = $("kbn5-nav-cart");
  const profileButton = $("kbn5-nav-profile");
  const menu = $("kbn5-mobile-menu");
  const menuButton = $("kbn5-menu-toggle");

  function closeMenu() {
    if (menu) menu.classList.remove("is-open");
    if (menuButton) menuButton.setAttribute("aria-expanded", "false");
  }

  if (cartButton) {
    cartButton.addEventListener("click", () => {
      closeMenu();

      const cart = window.KBN5CartUI;
      if (cart && typeof cart.open === "function") {
        cart.open();
        return;
      }

      const cartTarget =
        $("kbn5-cart-drawer") ||
        $("kbn5-cart-panel") ||
        $("cart-drawer");

      if (cartTarget) {
        cartTarget.hidden = false;
        cartTarget.classList.add("is-open");
      } else {
        setConnectionStatus("Cart panel is not connected yet.", "warning");
      }
    });
  }

  if (profileButton) {
    profileButton.addEventListener("click", () => {
      closeMenu();

      const profileTarget =
        $("kbn5-profile-panel") ||
        $("kbn5-profile-section") ||
        $("profile-section");

      if (profileTarget) {
        profileTarget.hidden = false;
        profileTarget.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });
        return;
      }

      setConnectionStatus("Profile section is not connected yet.", "warning");
    });
  }

  document.querySelectorAll("#kbn5-mobile-menu a").forEach((link) => {
    link.addEventListener("click", closeMenu);
  });
}

/* Re-run setup through the existing public initializer */
const previousInitialize = window.KBN5Frontend.initialize;

window.KBN5Frontend.initialize = function () {
  if (typeof previousInitialize === "function") {
    previousInitialize();
  }
  initializeQuickActions();
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeQuickActions, {
    once: true
  });
} else {
  initializeQuickActions();
}
