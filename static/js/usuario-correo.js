document.addEventListener("DOMContentLoaded", function () {
    var modal = document.querySelector("[data-modal-correo]");
    if (!modal) return;

    var abrir = document.querySelector("[data-abrir-correo]");
    var formulario = modal.querySelector("[data-correo-formulario]");
    var campo = formulario.querySelector("[name='email']");
    var correoActual = document.querySelector("[data-correo-actual]");
    var guardar = modal.querySelector("[data-correo-guardar]");
    var cancelar = modal.querySelector("[data-correo-cancelar]");
    var errorCampo = modal.querySelector("[data-correo-error]");
    var errorGeneral = modal.querySelector("[data-correo-error-general]");
    var aviso = document.querySelector("[data-correo-guardado]");
    var valorGuardado = campo.value;
    var enviando = false;

    function limpiarErrores() {
        errorCampo.hidden = true;
        errorGeneral.hidden = true;
        campo.removeAttribute("aria-invalid");
        campo.removeAttribute("aria-describedby");
    }

    abrir.addEventListener("click", function () {
        campo.value = valorGuardado;
        limpiarErrores();
        aviso.hidden = true;
        document.documentElement.classList.add("modal-abierto");
        modal.showModal();
        campo.focus();
    });

    cancelar.addEventListener("click", function () { modal.close(); });
    modal.addEventListener("cancel", function (evento) {
        if (enviando) evento.preventDefault();
    });
    modal.addEventListener("close", function () {
        document.documentElement.classList.remove("modal-abierto");
        abrir.focus();
    });

    formulario.addEventListener("submit", async function (evento) {
        evento.preventDefault();
        if (enviando) return;
        limpiarErrores();
        enviando = true;
        guardar.disabled = true;
        cancelar.disabled = true;
        campo.readOnly = true;
        formulario.setAttribute("aria-busy", "true");
        try {
            var respuesta = await fetch(formulario.action, {
                method: "POST",
                body: new FormData(formulario),
                credentials: "same-origin",
                cache: "no-store",
                headers: { "Accept": "application/json" }
            });
            if (respuesta.redirected || !(respuesta.headers.get("Content-Type") || "").includes("application/json")) {
                throw new Error("No se pudo guardar el correo. Revisá tu sesión y volvé a intentar");
            }
            var datos = await respuesta.json();
            if (!respuesta.ok) {
                if (!datos.errores) throw new Error("No se pudo guardar el correo");
                if (datos.errores.email) {
                    errorCampo.textContent = datos.errores.email.join(" ");
                    errorCampo.hidden = false;
                    campo.setAttribute("aria-invalid", "true");
                    campo.setAttribute("aria-describedby", errorCampo.id);
                }
                if (datos.errores.__all__) {
                    errorGeneral.textContent = datos.errores.__all__.join(" ");
                    errorGeneral.hidden = false;
                }
                return;
            }
            if (typeof datos.email !== "string") throw new Error("No se pudo confirmar el correo guardado");
            valorGuardado = datos.email;
            correoActual.textContent = valorGuardado || "Sin informar";
            aviso.textContent = datos.mensaje;
            aviso.hidden = false;
            modal.close();
        } catch (error) {
            errorGeneral.textContent = error.message;
            errorGeneral.hidden = false;
        } finally {
            enviando = false;
            guardar.disabled = false;
            cancelar.disabled = false;
            campo.readOnly = false;
            formulario.removeAttribute("aria-busy");
            if (modal.open) campo.focus();
        }
    });
});
