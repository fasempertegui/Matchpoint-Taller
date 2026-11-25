document.addEventListener("DOMContentLoaded", () => {
    const gestion = document.querySelector("[data-gestion-roles]");
    if (gestion) {
        const abrirRoles = document.querySelector("[data-abrir-roles]");
        const menuRoles = abrirRoles.closest("details");

        const abrirDialogoRoles = () => {
            gestion.showModal();
            if (window.Mensajes) window.Mensajes.sincronizarContenedor(gestion);
        };

        abrirRoles.addEventListener("click", () => {
            menuRoles.open = false;
            abrirDialogoRoles();
        });
        gestion.addEventListener("close", () => {
            menuRoles.querySelector("summary").focus({ preventScroll: true });
        });
        if (window.location.hash === "#roles") abrirDialogoRoles();
    }

    const modalEstado = document.querySelector("[data-modal-estado]");
    if (!modalEstado) return;

    const abrirEstado = document.querySelector("[data-abrir-estado]");
    const menu = abrirEstado.closest("details");
    const formularioEstado = modalEstado.querySelector("[data-estado-formulario]");
    const confirmarEstado = modalEstado.querySelector("[data-estado-confirmar]");
    const cancelarEstado = modalEstado.querySelector("[data-estado-cancelar]");
    let enviandoEstado = false;

    abrirEstado.addEventListener("click", () => {
        menu.open = false;
        document.documentElement.classList.add("modal-abierto");
        modalEstado.showModal();
    });
    cancelarEstado.addEventListener("click", () => modalEstado.close());
    modalEstado.addEventListener("cancel", (evento) => {
        if (enviandoEstado) evento.preventDefault();
    });
    modalEstado.addEventListener("close", () => {
        document.documentElement.classList.remove("modal-abierto");
        menu.querySelector("summary").focus({ preventScroll: true });
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
