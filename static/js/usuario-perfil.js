document.addEventListener("DOMContentLoaded", () => {
    const gestion = document.querySelector("[data-gestion-roles]");
    if (gestion && window.location.hash === "#roles") {
        gestion.open = true;
    }
});
