document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-modal-horarios]").forEach(function (modal) {
        var tipo = modal.dataset.modalHorarios;
        var botonAbrir = document.querySelector('[data-abrir-modal="' + tipo + '"]');
        if (!botonAbrir) return;

        var htmlInicial = modal.innerHTML;
        var enviando = false;
        var cargando = false;
        var devolverFoco = botonAbrir;

        async function solicitarFormulario(url, opciones) {
            var respuesta = await fetch(url, {
                cache: "no-store",
                headers: { "Accept": "application/json" },
                ...opciones
            });
            if (respuesta.redirected || !(respuesta.headers.get("Content-Type") || "").includes("application/json")) {
                throw new Error("No se pudo completar la operación. Actualizá la página y volvé a intentar.");
            }
            return respuesta.json();
        }

        function mostrarContenido(datos) {
            if (typeof datos.html !== "string") {
                throw new Error("No se pudo procesar la respuesta del servidor.");
            }
            modal.innerHTML = datos.html;
            modal.classList.toggle("horario-modal-revision", Boolean(datos.revision));
            actualizarFranjas();
            marcarCamposInvalidos();
        }

        function abrirModal() {
            document.documentElement.classList.add("modal-abierto");
            modal.showModal();
        }

        function actualizarFranjas() {
            var formulario = modal.querySelector("[data-horario-especial]");
            if (!formulario) return;
            var cerrada = formulario.querySelector("[name='cerrada']");
            var franjas = formulario.querySelector("[data-franjas-especiales]");
            var segundaFranja = formulario.querySelector("[name='segunda_franja']");
            var horarioSegundaFranja = formulario.querySelector("[data-segunda-franja]");
            if (!cerrada || !franjas || !segundaFranja || !horarioSegundaFranja) return;

            var estaCerrada = cerrada.checked;
            franjas.disabled = estaCerrada;
            franjas.hidden = estaCerrada;
            horarioSegundaFranja.disabled = estaCerrada || !segundaFranja.checked;
            horarioSegundaFranja.hidden = !segundaFranja.checked;
        }

        function marcarCamposInvalidos() {
            modal.querySelectorAll(".grupo-campo").forEach(function (grupo) {
                var errores = grupo.querySelector("[id$='_errores']");
                if (!errores) return;
                var control = grupo.querySelector("select, input:not([type='hidden']), textarea");
                if (!control) return;
                control.setAttribute("aria-invalid", "true");
                control.setAttribute("aria-describedby", errores.id);
            });
        }

        function enfocarContenido(estado) {
            var contenido = modal.querySelector(".modal-confirmacion-contenido");
            if (contenido) contenido.scrollTop = 0;

            if (estado.errores) {
                var invalido = modal.querySelector("[aria-invalid='true']:not(:disabled)");
                if (invalido) {
                    invalido.focus();
                    return;
                }
            }
            if (estado.revision) {
                var titulo = modal.querySelector("[data-modal-titulo]");
                if (titulo) {
                    titulo.focus();
                    return;
                }
            }
            var primerCampo = modal.querySelector(
                ".modal-confirmacion-contenido select:not(:disabled), "
                + ".modal-confirmacion-contenido input:not([type='hidden']):not(:disabled), "
                + ".modal-confirmacion-contenido textarea:not(:disabled)"
            );
            var destino = primerCampo || modal.querySelector("[data-modal-titulo]");
            if (destino) destino.focus();
        }

        function restaurarInicial() {
            modal.innerHTML = htmlInicial;
            modal.classList.remove("horario-modal-revision");
            actualizarFranjas();
        }

        actualizarFranjas();

        botonAbrir.addEventListener("click", function () {
            if (cargando) return;
            devolverFoco = botonAbrir;
            restaurarInicial();
            abrirModal();
            enfocarContenido({ errores: false, revision: false });
        });

        var configuracionFila = tipo === "horario-especial"
            ? {
                selector: "[data-modal-horario-fila]",
                plantillaError: "[data-error-carga-horario]",
                mensajeError: "No se pudo abrir el horario especial. Volvé a intentar."
            }
            : {
                selector: "[data-modal-feriado-fila]",
                plantillaError: "[data-error-carga-feriado]",
                mensajeError: "No se pudo abrir el feriado. Volvé a intentar."
            };
        var errorCarga = document.querySelector(configuracionFila.plantillaError);

        document.addEventListener("click", async function (evento) {
            var enlace = evento.target.closest(configuracionFila.selector);
            if (!enlace) return;
            if (evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey) return;
            evento.preventDefault();
            if (cargando || modal.open) return;

            devolverFoco = enlace;
            devolverFoco.focus({ preventScroll: true });
            cargando = true;
            var datos = {};
            try {
                datos = await solicitarFormulario(enlace.href);
                mostrarContenido(datos);
            } catch (error) {
                modal.replaceChildren(errorCarga.content.cloneNode(true));
                modal.querySelector("[role='alert']").textContent = configuracionFila.mensajeError;
                modal.classList.remove("horario-modal-revision");
            } finally {
                cargando = false;
            }
            if (!document.querySelector("[data-modal-horarios][open]")) {
                abrirModal();
                enfocarContenido(datos);
            }
        });

        modal.addEventListener("click", function (evento) {
            if (evento.target.closest("[data-modal-cerrar]") && !enviando) {
                modal.close();
            }
        });

        modal.addEventListener("change", function (evento) {
            if (evento.target.matches("[name='cerrada'], [name='segunda_franja']")) {
                actualizarFranjas();
            }
        });

        modal.addEventListener("cancel", function (evento) {
            if (enviando) evento.preventDefault();
        });

        modal.addEventListener("close", function () {
            document.documentElement.classList.remove("modal-abierto");
            modal.classList.remove("horario-modal-revision");
            devolverFoco.focus({ preventScroll: true });
        });

        modal.addEventListener("submit", async function (evento) {
            var formulario = evento.target.closest("[data-modal-formulario]");
            if (!formulario) return;
            evento.preventDefault();
            if (enviando) return;

            var submitter = evento.submitter || formulario.querySelector('button[type="submit"][name="paso"]');
            var datosFormulario = submitter ? new FormData(formulario, submitter) : new FormData(formulario);
            if (!datosFormulario.has("paso") && submitter && submitter.name) {
                datosFormulario.append(submitter.name, submitter.value);
            }

            var errorGeneral = formulario.querySelector("[data-modal-error-general]");
            if (errorGeneral) errorGeneral.hidden = true;

            enviando = true;
            var guardado = false;
            var botones = Array.from(formulario.querySelectorAll("button"));
            botones.forEach(function (boton) { boton.disabled = true; });
            formulario.setAttribute("aria-busy", "true");

            try {
                var datos = await solicitarFormulario(formulario.action, {
                    method: "POST",
                    body: datosFormulario
                });
                if (datos.ok) {
                    guardado = true;
                    window.location.reload();
                    return;
                }
                mostrarContenido(datos);
                enfocarContenido({
                    errores: Boolean(datos.errores),
                    revision: Boolean(datos.revision)
                });
            } catch (error) {
                if (errorGeneral) {
                    errorGeneral.textContent = error.message;
                    errorGeneral.hidden = false;
                    errorGeneral.scrollIntoView({ block: "nearest" });
                }
            } finally {
                if (!guardado) {
                    enviando = false;
                    var formularioActual = modal.querySelector("[data-modal-formulario]");
                    if (formularioActual) {
                        formularioActual.removeAttribute("aria-busy");
                        formularioActual.querySelectorAll("button").forEach(function (boton) {
                            boton.disabled = false;
                        });
                    }
                }
            }
        });
    });
});
