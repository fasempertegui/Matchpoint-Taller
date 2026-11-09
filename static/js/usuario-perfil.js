document.addEventListener("DOMContentLoaded", () => {
    const gestion = document.querySelector("[data-gestion-roles]");
    if (gestion && window.location.hash === "#roles") {
        gestion.open = true;
    }

    const modalEstado = document.querySelector("[data-modal-estado]");
    if (!modalEstado) return;

    const abrirEstado = document.querySelector("[data-abrir-estado]");
    const formularioEstado = modalEstado.querySelector("[data-estado-formulario]");
    const confirmarEstado = modalEstado.querySelector("[data-estado-confirmar]");
    const cancelarEstado = modalEstado.querySelector("[data-estado-cancelar]");
    let enviandoEstado = false;

    abrirEstado.addEventListener("click", () => {
        document.documentElement.classList.add("modal-abierto");
        modalEstado.showModal();
    });
    cancelarEstado.addEventListener("click", () => modalEstado.close());
    modalEstado.addEventListener("cancel", (evento) => {
        if (enviandoEstado) evento.preventDefault();
    });
    modalEstado.addEventListener("close", () => {
        document.documentElement.classList.remove("modal-abierto");
        abrirEstado.focus();
    });
    formularioEstado.addEventListener("submit", (evento) => {
        if (enviandoEstado) {
            evento.preventDefault();
            return;
        }
        enviandoEstado = true;
        confirmarEstado.disabled = true;
        cancelarEstado.disabled = true;
        formularioEstado.setAttribute("aria-busy", "true");
    });
});
