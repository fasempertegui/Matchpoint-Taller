document.addEventListener("DOMContentLoaded", function () {
    var modal = document.querySelector("[data-modal-confirmacion]");
    if (!modal) return;
    var titulo = modal.querySelector("[data-modal-titulo]");
    var mensaje = modal.querySelector("[data-modal-mensaje]");
    var detalle = modal.querySelector("[data-modal-confirmar-detalle]");
    var botonConfirmar = modal.querySelector("[data-modal-confirmar]");
    var confirmacionPendiente = null;
    var formularioAutorizado = null;

    window.addEventListener("pageshow", function () {
        document.querySelectorAll("form[data-enviando-confirmacion]").forEach(function (formulario) {
            delete formulario.dataset.enviandoConfirmacion;
            formulario.removeAttribute("aria-busy");
        });
    });

    document.addEventListener("submit", function (evento) {
        var formulario = evento.target;
        if (!formulario.matches("form[data-confirmar]") || evento.defaultPrevented) return;
        if (evento.submitter && evento.submitter.hasAttribute("data-sin-confirmar")) return;

        if (formulario.dataset.enviandoConfirmacion === "1") {
            evento.preventDefault();
            return;
        }

        if (formularioAutorizado === formulario) {
            formularioAutorizado = null;
            formulario.dataset.enviandoConfirmacion = "1";
            formulario.setAttribute("aria-busy", "true");
            return;
        }

        var selector = formulario.dataset.confirmarSi;
        if (selector && !formulario.querySelector(selector)) return;

        evento.preventDefault();
        if (confirmacionPendiente) return;

        var disparador = evento.submitter || null;
        var menu = disparador ? disparador.closest("details[data-menu-contextual]") : null;
        if (menu) menu.open = false;
        var focoRetorno = menu ? (menu.querySelector("summary") || disparador) : disparador;

        confirmacionPendiente = {
            formulario: formulario,
            boton: disparador,
            foco: focoRetorno,
        };
        titulo.textContent = formulario.dataset.confirmarTitulo || "Confirmar acción";
        mensaje.textContent = formulario.dataset.confirmar;
        var plantilla = formulario.querySelector("template[data-confirmar-detalle]");
        detalle.replaceChildren();
        if (plantilla) detalle.append(plantilla.content.cloneNode(true));
        detalle.hidden = !plantilla;
        botonConfirmar.textContent = formulario.dataset.confirmarBoton || "Confirmar";
        var esPeligrosa = formulario.hasAttribute("data-confirmar-peligro");
        var esAdvertencia = !esPeligrosa && formulario.hasAttribute("data-confirmar-advertencia");
        modal.classList.toggle("modal-peligro", esPeligrosa);
        modal.classList.toggle("modal-advertencia", esAdvertencia);
        botonConfirmar.classList.toggle("boton-confirmar-peligro", esPeligrosa);
        botonConfirmar.classList.toggle("boton-confirmar-advertencia", esAdvertencia);
        botonConfirmar.classList.toggle("boton-primario", !esPeligrosa && !esAdvertencia);
        modal.returnValue = "cancelar";
        document.documentElement.classList.add("modal-abierto");
        modal.showModal();
    });

    modal.addEventListener("close", function () {
        var confirmacion = confirmacionPendiente;
        confirmacionPendiente = null;
        document.documentElement.classList.remove("modal-abierto");
        if (modal.returnValue !== "confirmar" || !confirmacion) {
            if (confirmacion && confirmacion.foco && confirmacion.foco.isConnected) {
                confirmacion.foco.focus({ preventScroll: true });
            }
            return;
        }

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
