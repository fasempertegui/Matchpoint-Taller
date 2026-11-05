document.addEventListener("DOMContentLoaded", function () {
    function preparar(raiz) {
        raiz.querySelectorAll("[data-clase-pasos]").forEach(function (formulario) {
            if (formulario.dataset.pasosPreparados) return;
            formulario.dataset.pasosPreparados = "true";
            var paso = 0;
            var confirmacion = "";
            var solicitud = null;
            var resultadoCreacion = null;
            var errorCampo = formulario.querySelector("[data-clase-error]");
            var avisoProfesores = formulario.querySelector("[data-clase-profesores-error]");
            var botonRevision = formulario.querySelector("[data-clase-revisar]");
            var botonConfirmar = formulario.querySelector("[data-clase-confirmar]");

            function cantidad(tipo) {
                return formulario.querySelectorAll('[data-tipo="' + tipo + '"] [data-persona]').length;
            }

            function actualizarParticipantes() {
                botonRevision.textContent = cantidad("participantes") ? "Siguiente" : "Continuar sin participantes";
            }

            function mostrar(indice) {
                paso = indice;
                formulario.querySelector("[data-clase-atras]").hidden = paso === 0;
                formulario.querySelectorAll("[data-clase-paso]").forEach(function (seccion) {
                    seccion.hidden = Number(seccion.dataset.clasePaso) !== paso;
                });
                formulario.querySelector("[data-clase-progreso]").setAttribute("aria-valuenow", paso + 1);
                formulario.querySelector("[data-clase-numero]").textContent = "Paso " + (paso + 1) + " de 3";
                formulario.querySelectorAll("[data-clase-indicador]").forEach(function (indicador) {
                    indicador.classList.toggle("agenda-clase-segmento-completo", Number(indicador.dataset.claseIndicador) <= paso);
                });
                var seccion = formulario.querySelector('[data-clase-paso="' + paso + '"]');
                var foco = seccion.querySelector("[data-busqueda], [data-clase-resumen-titulo]");
                if (foco && formulario.closest("details").open) foco.focus({preventScroll: true});
                seccion.querySelectorAll("[data-observaciones]").forEach(function (bloque) {
                    bloque.dispatchEvent(new Event("observaciones:ajustar"));
                });
            }

            function informar(mensaje, profesores = false) {
                if (profesores) {
                    errorCampo.hidden = true;
                    avisoProfesores.textContent = mensaje;
                    avisoProfesores.hidden = false;
                    avisoProfesores.focus({preventScroll: true});
                    return;
                }
                errorCampo.textContent = mensaje;
                errorCampo.hidden = false;
                errorCampo.focus({preventScroll: true});
            }

            function ocupar(ocupado) {
                if (ocupado) formulario.setAttribute("aria-busy", "true");
                else formulario.removeAttribute("aria-busy");
                formulario.querySelectorAll("[data-clase-siguiente], [data-clase-atras], [data-clase-revisar], [data-clase-confirmar]").forEach(function (boton) {
                    boton.disabled = ocupado;
                });
            }

            formulario.addEventListener("clase:seleccion", function () {
                confirmacion = "";
                errorCampo.hidden = true;
                if (cantidad("profesores")) avisoProfesores.hidden = true;
                actualizarParticipantes();
            });
            formulario.addEventListener("input", function () { confirmacion = ""; });
            formulario.addEventListener("click", function (evento) {
                if (evento.target.closest("[data-clase-siguiente]")) {
                    if (!cantidad("profesores")) {
                        informar("Agregá al menos un profesor para continuar", true);
                        return;
                    }
                    errorCampo.hidden = true;
                    mostrar(1);
                }
                if (evento.target.closest("[data-clase-atras]")) {
                    errorCampo.hidden = true;
                    confirmacion = "";
                    mostrar(Math.max(0, paso - 1));
                }
            });
            formulario.addEventListener("reset", function () {
                if (solicitud) solicitud.abort();
                solicitud = null;
                confirmacion = "";
                resultadoCreacion = null;
                avisoProfesores.hidden = true;
                ocupar(false);
                formulario.querySelectorAll("[data-persona]").forEach(function (fila) { fila.remove(); });
                formulario.querySelector("[data-clase-resumen]").replaceChildren();
                formulario.dispatchEvent(new Event("clase:reiniciar"));
                errorCampo.hidden = true;
                mostrar(0);
            });
            formulario.addEventListener("clase:desmontar", function () {
                if (solicitud) solicitud.abort();
            }, {once: true});

            formulario.addEventListener("submit", async function (evento) {
                evento.preventDefault();
                if (formulario.getAttribute("aria-busy")) return;
                if (paso === 0) {
                    formulario.querySelector("[data-clase-siguiente]").click();
                    return;
                }
                if (resultadoCreacion) {
                    document.dispatchEvent(new CustomEvent("agenda:actualizar", {detail: resultadoCreacion}));
                    return;
                }
                var confirmar = paso === 2;
                if (confirmar && !confirmacion) {
                    informar("Los datos cambiaron. Volvé al paso anterior para revisar la clase");
                    return;
                }
                var control = new AbortController();
                solicitud = control;
                var datos = new FormData(formulario);
                var seleccion = new URLSearchParams(datos).toString();
                datos.set("paso", confirmar ? "confirmar" : "revisar");
                if (confirmar) datos.set("confirmacion", confirmacion);
                ocupar(true);
                errorCampo.hidden = true;
                botonRevision.textContent = "Revisando…";
                botonConfirmar.textContent = "Creando…";
                try {
                    var respuesta = await fetch(formulario.action, {
                        method: "POST", body: datos, headers: {"X-Agenda-Clase": "1"},
                        credentials: "same-origin", cache: "no-store", signal: control.signal,
                    });
                    if (respuesta.redirected || !(respuesta.headers.get("Content-Type") || "").includes("application/json")) {
                        throw new Error("No se pudo completar la solicitud. Revisá tu sesión y volvé a intentar");
                    }
                    var resultado = await respuesta.json();
                    if (!formulario.isConnected || solicitud !== control) return;
                    if (!confirmar && seleccion !== new URLSearchParams(new FormData(formulario)).toString()) {
                        informar("La selección cambió. Revisá la clase nuevamente");
                        return;
                    }
                    if (!respuesta.ok) {
                        confirmacion = "";
                        var errores = resultado.errores || {__all__: ["No se pudo completar la solicitud"]};
                        mostrar(errores.profesores ? 0 : 1);
                        informar(Object.values(errores).flat().join(" "), Boolean(errores.profesores));
                        return;
                    }
                    if (confirmar) {
                        resultadoCreacion = resultado;
                        document.dispatchEvent(new CustomEvent("agenda:actualizar", {detail: resultado}));
                    } else {
                        formulario.querySelector("[data-clase-resumen]").innerHTML = resultado.resumen;
                        confirmacion = resultado.confirmacion;
                        mostrar(2);
                    }
                } catch (error) {
                    if (error.name !== "AbortError" && formulario.isConnected && solicitud === control) informar(error.message);
                } finally {
                    if (solicitud === control) {
                        solicitud = null;
                        ocupar(false);
                        actualizarParticipantes();
                        botonConfirmar.textContent = resultadoCreacion ? "Actualizar agenda" : "Confirmar creación";
                        if (resultadoCreacion) {
                            formulario.querySelectorAll("[data-clase-atras], [data-cancelar-creacion]").forEach(function (boton) { boton.hidden = true; });
                        }
                    }
                }
            });
            actualizarParticipantes();
        });
    }
    preparar(document);
    document.addEventListener("clase:inicializar", function (evento) { preparar(evento.target); });
});
