document.addEventListener("DOMContentLoaded", function () {
    var modal = document.querySelector("[data-modal-confirmacion]");
    var titulo = modal.querySelector("[data-modal-titulo]");
    var mensaje = modal.querySelector("[data-modal-mensaje]");
    var botonConfirmar = modal.querySelector("[data-modal-confirmar]");
    var confirmacionPendiente = null;
    var formularioAutorizado = null;

    document.addEventListener("submit", function (evento) {
        var formulario = evento.target;
        if (!formulario.matches("form[data-confirmar]") || evento.defaultPrevented) return;

        if (formularioAutorizado === formulario) {
            formularioAutorizado = null;
            return;
        }

        var selector = formulario.dataset.confirmarSi;
        if (selector && !formulario.querySelector(selector)) return;

        evento.preventDefault();
        if (confirmacionPendiente) return;

        confirmacionPendiente = { formulario: formulario, boton: evento.submitter };
        titulo.textContent = formulario.dataset.confirmarTitulo || "Confirmar acción";
        mensaje.textContent = formulario.dataset.confirmar;
        botonConfirmar.textContent = formulario.dataset.confirmarBoton || "Confirmar";
        modal.returnValue = "cancelar";
        document.documentElement.classList.add("modal-abierto");
        modal.showModal();
    });

    modal.addEventListener("close", function () {
        var confirmacion = confirmacionPendiente;
        confirmacionPendiente = null;
        document.documentElement.classList.remove("modal-abierto");
        if (modal.returnValue !== "confirmar" || !confirmacion) return;

        formularioAutorizado = confirmacion.formulario;
        try {
            if (confirmacion.boton) {
                confirmacion.formulario.requestSubmit(confirmacion.boton);
            } else {
                confirmacion.formulario.requestSubmit();
            }
        } finally {
            formularioAutorizado = null;
        }
    });
});
