document.addEventListener("DOMContentLoaded", function () {
    var modal = document.querySelector("[data-modal-restablecer]");
    if (!modal) return;

    var abrir = document.querySelector("[data-abrir-restablecimiento]");
    var formulario = modal.querySelector("[data-restablecer-formulario]");
    var titulo = modal.querySelector("[data-restablecer-titulo]");
    var confirmacion = modal.querySelector("[data-restablecer-confirmacion]");
    var resultado = modal.querySelector("[data-restablecer-resultado]");
    var clave = modal.querySelector("[data-restablecer-clave]");
    var error = modal.querySelector("[data-restablecer-error]");
    var confirmar = modal.querySelector("[data-restablecer-confirmar]");
    var cerrar = modal.querySelector("[data-restablecer-cerrar]");
    var copiar = modal.querySelector("[data-restablecer-copiar]");
    var iconoCopiar = copiar.querySelector("[data-icono-copiar]");
    var iconoCopiado = copiar.querySelector("[data-icono-copiado]");
    var temporizadorCopia;

    function restablecerIconoCopia() {
        clearTimeout(temporizadorCopia);
        iconoCopiar.hidden = false;
        iconoCopiado.hidden = true;
        copiar.setAttribute("aria-label", "Copiar contraseña");
    }
    var enviando = false;

    abrir.addEventListener("click", function () {
        titulo.textContent = "Restablecer contraseña";
        confirmacion.hidden = false;
        resultado.hidden = true;
        confirmar.hidden = false;
        error.hidden = true;
        cerrar.textContent = "Cancelar";
        cerrar.classList.remove("boton-primario");
        cerrar.classList.add("boton-secundario");
        copiar.disabled = false;
        restablecerIconoCopia();
        document.documentElement.classList.add("modal-abierto");
        modal.showModal();
    });

    cerrar.addEventListener("click", function () { modal.close(); });
    modal.addEventListener("cancel", function (evento) {
        if (enviando) evento.preventDefault();
    });
    modal.addEventListener("close", function () {
        clave.textContent = "";
        restablecerIconoCopia();
        document.documentElement.classList.remove("modal-abierto");
        abrir.focus();
    });

    copiar.addEventListener("click", async function () {
        var texto = clave.textContent;
        copiar.disabled = true;
        error.hidden = true;
        try {
            await navigator.clipboard.writeText(texto);
            if (!modal.open || clave.textContent !== texto) return;
            restablecerIconoCopia();
            iconoCopiar.hidden = true;
            iconoCopiado.hidden = false;
            copiar.setAttribute("aria-label", "Contraseña copiada");
            temporizadorCopia = setTimeout(restablecerIconoCopia, 5000);
        } catch (fallo) {
            if (!modal.open || clave.textContent !== texto) return;
            error.textContent = "No se pudo copiar la contraseña. Podés seleccionarla y copiarla manualmente";
            error.hidden = false;
        } finally {
            copiar.disabled = false;
        }
    });

    formulario.addEventListener("submit", async function (evento) {
        evento.preventDefault();
        if (enviando || !resultado.hidden) return;
        enviando = true;
        confirmar.disabled = true;
        cerrar.disabled = true;
        error.hidden = true;
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
                throw new Error("No se pudo completar la solicitud. Revisá tu sesión y el estado de la cuenta antes de volver a intentar");
            }
            var datos = await respuesta.json();
            if (!respuesta.ok) throw new Error(datos.error || "No se pudo restablecer la contraseña");
            if (typeof datos.contrasena !== "string" || !datos.contrasena) {
                throw new Error("No se recibió la contraseña provisoria. Revisá el estado de la cuenta antes de volver a intentar");
            }
            clave.textContent = datos.contrasena;
            titulo.textContent = "Contraseña restablecida";
            confirmacion.hidden = true;
            resultado.hidden = false;
            confirmar.hidden = true;
            cerrar.textContent = "Cerrar";
            cerrar.classList.remove("boton-secundario");
            cerrar.classList.add("boton-primario");
            document.querySelector("[data-cambio-pendiente]").hidden = false;
        } catch (fallo) {
            error.textContent = fallo.message;
            error.hidden = false;
        } finally {
            enviando = false;
            confirmar.disabled = false;
            cerrar.disabled = false;
            formulario.removeAttribute("aria-busy");
            if (resultado.hidden) cerrar.focus();
            else copiar.focus();
        }
    });
});
