const modalMovimientos = document.getElementById("movimientos-financieros");
const botonMovimientos = document.querySelector("[data-abrir-movimientos]");
const menuMovimientos = botonMovimientos.closest("details");

botonMovimientos.addEventListener("click", () => {
    menuMovimientos.open = false;
    modalMovimientos.showModal();
});

modalMovimientos.addEventListener("close", () => {
    menuMovimientos.querySelector("summary").focus({ preventScroll: true });
});

if (modalMovimientos.hasAttribute("data-abrir-inicialmente")) {
    document.addEventListener("DOMContentLoaded", () => {
        const panelPagos = document.querySelector('[data-panel="pagos-movimientos"]');
        if (!panelPagos || !panelPagos.hidden) {
            modalMovimientos.showModal();
        }
    });
}
