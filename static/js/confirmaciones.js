document.addEventListener("DOMContentLoaded", function () {
    var modal = document.querySelector("[data-modal-confirmacion]");
    var titulo = modal.querySelector("[data-modal-titulo]");
    var mensaje = modal.querySelector("[data-modal-mensaje]");
    var botonConfirmar = modal.querySelector("[data-modal-confirmar]");
    var confirmacionPendiente = null;
    var formularioAutorizado = null;

    document.addEventListener("submit", async function (evento) {
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
        if (formulario.dataset.confirmarRevision) {
            var boton = evento.submitter;
            var errorCampo = formulario.querySelector("[data-confirmar-error]");
            if (!errorCampo) {
                errorCampo = document.createElement("p");
                errorCampo.className = "error-campo";
                errorCampo.dataset.confirmarError = "";
                errorCampo.setAttribute("role", "alert");
                formulario.append(errorCampo);
            }
            errorCampo.hidden = true;
            var datos = new FormData(formulario);
            var seleccion = new URLSearchParams(datos).toString();
            formulario.setAttribute("aria-busy", "true");
            if (boton) boton.disabled = true;
            try {
                var respuesta = await fetch(formulario.dataset.confirmarRevision, {
                    method: "POST", body: datos,
                    headers: {"X-Agenda-Anulacion": "1"},
                    credentials: "same-origin", cache: "no-store",
                });
                if (respuesta.redirected || !(respuesta.headers.get("Content-Type") || "").includes("application/json")) {
                    throw new Error("No se pudo revisar la anulación. Revisá tu sesión y volvé a intentar.");
                }
                var revision = await respuesta.json();
                if (!respuesta.ok) throw new Error(revision.error || "No se pudo revisar la anulación.");
                var opcion = formulario.closest("details");
                if (!formulario.isConnected || (opcion && !opcion.open)
                    || seleccion !== new URLSearchParams(new FormData(formulario)).toString()) {
                    confirmacionPendiente = null;
                    return;
                }
                formulario.elements.confirmacion.value = revision.confirmacion;
                formulario.dataset.confirmar = revision.mensaje;
            } catch (error) {
                confirmacionPendiente = null;
                if (formulario.isConnected) {
                    errorCampo.textContent = error.message;
                    errorCampo.hidden = false;
                }
                return;
            } finally {
                formulario.removeAttribute("aria-busy");
                if (boton) boton.disabled = false;
            }
        }
        titulo.textContent = formulario.dataset.confirmarTitulo || "Confirmar acción";
        mensaje.textContent = formulario.dataset.confirmar;
        botonConfirmar.textContent = formulario.dataset.confirmarBoton || "Confirmar";
        var esPeligrosa = formulario.hasAttribute("data-confirmar-peligro");
        botonConfirmar.classList.toggle("boton-confirmar-peligro", esPeligrosa);
        botonConfirmar.classList.toggle("boton-primario", !esPeligrosa);
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
