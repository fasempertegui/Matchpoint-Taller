document.addEventListener("DOMContentLoaded", function () {
    var modal = document.querySelector("[data-modal-formulario-dialog]");
    if (!modal) return;

    var cargando = false;
    var enviando = false;
    var devolverFoco = null;

    async function solicitar(url, opciones) {
        var respuesta = await fetch(url, Object.assign({
            cache: "no-store",
            credentials: "same-origin",
            headers: {
                "X-Modal-Formulario": "1",
                "Accept": "application/json",
            },
        }, opciones || {}));
        var tipo = respuesta.headers.get("Content-Type") || "";
        if (respuesta.redirected || !tipo.includes("application/json")) {
            return { redirigir: respuesta.url || url };
        }
        var datos = await respuesta.json();
        return { ok: respuesta.ok, status: respuesta.status, datos: datos };
    }

    function aplicarVariantes(datos) {
        var form = modal.querySelector("[data-modal-formulario-form]");
        var esPeligro = Boolean((datos && datos.peligro) || (form && form.hasAttribute("data-modal-peligro")));
        var esAmplio = Boolean((datos && datos.amplio) || (form && form.hasAttribute("data-modal-amplio")));
        modal.classList.toggle("modal-peligro", esPeligro);
        modal.classList.toggle("modal-amplio", esAmplio);
    }

    function marcarCamposInvalidos() {
        modal.querySelectorAll(".grupo-campo").forEach(function (grupo) {
            var error = grupo.querySelector(".error-campo");
            if (!error) return;
            var control = grupo.querySelector("select, input:not([type='hidden']), textarea");
            if (!control) return;
            if (!error.id && control.id) {
                error.id = control.id + "_error";
            }
            control.setAttribute("aria-invalid", "true");
            if (error.id) {
                control.setAttribute("aria-describedby", error.id);
            }
        });
    }

    function enfocarContenido(conErrores) {
        var cuerpo = modal.querySelector(".modal-cuerpo");
        if (cuerpo) cuerpo.scrollTop = 0;

        if (conErrores) {
            var invalido = modal.querySelector("[aria-invalid='true']:not(:disabled)");
            if (invalido) {
                invalido.focus();
                return;
            }
        }
        var primerCampo = modal.querySelector(
            ".modal-cuerpo select:not(:disabled), "
            + ".modal-cuerpo input:not([type='hidden']):not(:disabled), "
            + ".modal-cuerpo textarea:not(:disabled)"
        );
        var destino = primerCampo || modal.querySelector("[data-modal-titulo]");
        if (destino) destino.focus();
    }

    function renderizar(datos) {
        if (!datos || typeof datos.html !== "string") {
            throw new Error("No se pudo cargar el formulario. Actualizá la página y volvé a intentar.");
        }
        modal.innerHTML = datos.html;
        aplicarVariantes(datos);
        marcarCamposInvalidos();
        modal.dispatchEvent(new CustomEvent("observaciones:inicializar", { bubbles: true }));
        modal.dispatchEvent(new CustomEvent("modal-formulario:cargado", { bubbles: true }));
    }

    function mostrarErrorGeneral(mensaje) {
        var contenedor = modal.querySelector("[data-modal-error-general]");
        if (!contenedor) return;
        contenedor.textContent = mensaje;
        contenedor.hidden = false;
    }

    function abrirDialogo() {
        if (!modal.open) {
            document.documentElement.classList.add("modal-abierto");
            modal.showModal();
        }
    }

    function cerrarDialogo() {
        if (modal.open) {
            modal.close("cancelar");
        }
    }

    document.addEventListener("click", async function (evento) {
        var disparador = evento.target.closest("[data-abrir-modal-url]");
        if (!disparador) return;
        if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;

        var url = disparador.dataset.abrirModalUrl || disparador.getAttribute("href");
        if (!url) return;

        evento.preventDefault();
        if (cargando || enviando) return;

        cargando = true;
        devolverFoco = disparador;
        disparador.setAttribute("aria-busy", "true");
        try {
            var resultado = await solicitar(url, { method: "GET" });
            if (resultado.redirigir) {
                window.location.assign(resultado.redirigir);
                return;
            }
            if (resultado.datos && resultado.datos.error) {
                window.location.assign(url);
                return;
            }
            renderizar(resultado.datos);
            abrirDialogo();
            enfocarContenido(Boolean(resultado.datos.errores));
        } catch (error) {
            window.location.assign(url);
        } finally {
            cargando = false;
            disparador.removeAttribute("aria-busy");
        }
    });

    modal.addEventListener("click", function (evento) {
        if (evento.target.closest("[data-modal-cerrar]")) {
            cerrarDialogo();
        }
    });

    modal.addEventListener("submit", async function (evento) {
        var formulario = evento.target.closest("[data-modal-formulario-form]");
        if (!formulario) return;

        evento.preventDefault();
        if (enviando) return;

        var accion = formulario.getAttribute("action") || window.location.href;
        var metodo = (formulario.getAttribute("method") || "post").toUpperCase();
        var datosFormulario = new FormData(formulario);
        if (evento.submitter && evento.submitter.name) {
            datosFormulario.append(evento.submitter.name, evento.submitter.value || "");
        }

        var botonEnviar = evento.submitter || formulario.querySelector("[data-modal-enviar]");
        enviando = true;
        formulario.setAttribute("aria-busy", "true");
        if (botonEnviar) botonEnviar.disabled = true;

        try {
            var resultado = await solicitar(accion, {
                method: metodo,
                body: metodo === "GET" ? undefined : datosFormulario,
            });
            if (resultado.redirigir) {
                cerrarDialogo();
                window.location.assign(resultado.redirigir);
                return;
            }
            var datos = resultado.datos || {};
            if (resultado.ok && datos.ok) {
                cerrarDialogo();
                if (datos.redirect) {
                    var destino = new URL(datos.redirect, window.location.href);
                    if (
                        destino.origin === window.location.origin
                        && destino.pathname === window.location.pathname
                        && destino.search === window.location.search
                    ) {
                        if (destino.hash) {
                            window.history.replaceState(null, "", destino.href);
                        }
                        window.location.reload();
                    } else {
                        window.location.assign(destino.href);
                    }
                } else {
                    window.location.reload();
                }
                return;
            }
            if (typeof datos.html === "string") {
                renderizar(datos);
                enfocarContenido(true);
                return;
            }
            mostrarErrorGeneral(datos.error || "No se pudo completar la operación. Volvé a intentar.");
        } catch (error) {
            mostrarErrorGeneral("No se pudo conectar con el servidor. Volvé a intentar.");
        } finally {
            enviando = false;
            if (formulario.isConnected) {
                formulario.removeAttribute("aria-busy");
            }
            if (botonEnviar && botonEnviar.isConnected) {
                botonEnviar.disabled = false;
            }
        }
    });

    modal.addEventListener("close", function () {
        document.documentElement.classList.remove("modal-abierto");
        modal.innerHTML = "";
        modal.classList.remove("modal-peligro", "modal-amplio");
        var foco = devolverFoco;
        devolverFoco = null;
        if (foco && foco.isConnected) {
            foco.focus();
        }
    });
});
