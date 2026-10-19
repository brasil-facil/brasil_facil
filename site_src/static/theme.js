// Brasil Fácil: the Escuro / Claro switch in the header.
// With no choice saved, the site follows the device's own light or dark mode.

(function () {
  "use strict";

  var root = document.documentElement;
  var deviceDark = window.matchMedia("(prefers-color-scheme: dark)");
  var buttons = document.querySelectorAll("[data-theme-choice]");

  // The look actually on screen: the saved choice, or else the device's mode.
  function currentLook() {
    return root.dataset.theme || (deviceDark.matches ? "dark" : "light");
  }

  // Mark the button of the current look as pressed (that also styles it).
  function showPressed() {
    var look = currentLook();
    buttons.forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === look));
    });
  }

  function choose(look) {
    root.dataset.theme = look;
    try { localStorage.setItem("bf-theme", look); } catch (e) {}
    showPressed();
    // Tell the charts to redraw with the new colours.
    document.dispatchEvent(new Event("themechange"));
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () { choose(button.dataset.themeChoice); });
  });

  // If the reader never chose, follow the device when it switches mode.
  deviceDark.addEventListener("change", function () {
    showPressed();
    document.dispatchEvent(new Event("themechange"));
  });

  showPressed();
})();
