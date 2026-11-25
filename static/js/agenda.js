document.addEventListener("DOMContentLoaded", function () {
    var panel = document.querySelector("[data-agenda-detalle]");
    var contenido = panel && panel.querySelector("[data-agenda-contenido]");
    var aviso = panel && panel.querySelector("[data-agenda-aviso]");
    var solicitudActual = null;

    async function cargarDetalle(enlace, devolverFoco) {
        if (devolverFoco === undefined) devolverFoco = true;
        if (solicitudActual) solicitudActual.abort();
        var seleccionadoAnterior = document.querySelector(".agenda-turno-seleccionado");
        var cerrarDetalle = enlace.matches("[data-agenda-cerrar]");
        var solicitud = new AbortController();
        solicitudActual = solicitud;
        panel.setAttribute("aria-busy", "true");
        contenido.inert = true;
        aviso.hidden = true;
        aviso.textContent = "";
        var demoraAviso = window.setTimeout(function () {
            if (solicitud !== solicitudActual) return;
            aviso.textContent = "Cargando…";
            aviso.hidden = false;
        }, 300);
        var mensajeError = "No se pudo cargar el panel. Intentá nuevamente.";
        try {
            var respuesta = await fetch(enlace.href, {
                method: "GET",
                headers: { "X-Agenda-Detalle": "1" },
                credentials: "same-origin",
                cache: "no-store",
                signal: solicitud.signal,
            });
            if (respuesta.redirected) {
                mensajeError = "Tu acceso cambió o la sesión venció. Recargá la página para continuar.";
                throw new Error();
            }
            if (!respuesta.ok) {
                if (respuesta.status === 403) {
                    mensajeError = "No se pudo autorizar la consulta. Recargá la página para continuar.";
                } else if (respuesta.status === 400) {
                    try {
                        var cuerpo = await respuesta.json();
                        if (cuerpo && cuerpo.error) mensajeError = cuerpo.error;
                    } catch {
                        // Conserva el mensaje general si el cuerpo no es JSON.
                    }
                }
                throw new Error();
            }
            var seleccion = respuesta.headers.get("X-Agenda-Seleccion");
            if (!seleccion) throw new Error();
            var html = await respuesta.text();
            if (solicitud !== solicitudActual) return;
            contenido.innerHTML = html;
            contenido.inert = false;
            if (enlace.matches("[data-agenda-vista]")) {
                var titulo = contenido.querySelector("[data-agenda-titulo]");
                if (titulo) {
                    titulo.setAttribute("tabindex", "-1");
                    titulo.focus({ preventScroll: true });
                }
            }
            var destino = new URL(seleccion, window.location.href);
            document.querySelectorAll("[data-agenda-turno]").forEach(function (turno) {
                var urlTurno = new URL(turno.href);
                var activo = urlTurno.pathname === destino.pathname
                    && ["sede", "fecha", "cancha", "hora"].every(function (campo) {
                        return urlTurno.searchParams.get(campo) === destino.searchParams.get(campo);
                    }) && (!destino.searchParams.has("panel") || destino.searchParams.get("panel") === "historial");
                turno.classList.toggle("agenda-turno-seleccionado", activo);
                if (activo) turno.setAttribute("aria-current", "true");
                else turno.removeAttribute("aria-current");
            });
            window.history.replaceState(null, "", destino.href);
            if (cerrarDetalle && seleccionadoAnterior) {
                if (devolverFoco) {
                    seleccionadoAnterior.focus({ preventScroll: true });
                } else if (document.activeElement === seleccionadoAnterior) {
                    seleccionadoAnterior.blur();
                }
            }
        } catch (error) {
            if (error.name === "AbortError" || solicitud !== solicitudActual) return;
            var textoError = error instanceof TypeError
                ? "No se pudo conectar con el servidor. Revisá tu conexión e intentá nuevamente."
                : mensajeError;
            if (window.Mensajes) {
                window.Mensajes.mostrar({
                    texto: textoError,
                    nivel: "error",
                    clave: "agenda-panel-error",
                });
            }
        } finally {
            window.clearTimeout(demoraAviso);
            if (solicitud === solicitudActual) {
                aviso.hidden = true;
                aviso.textContent = "";
                panel.removeAttribute("aria-busy");
                contenido.inert = false;
            }
        }
    }

    document.addEventListener("click", function (evento) {
        var enlace = evento.target.closest("[data-agenda-turno], [data-agenda-cerrar], [data-agenda-vista]");
        if (!enlace || !panel || evento.defaultPrevented || evento.button !== 0 || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey) return;
        evento.preventDefault();
        cargarDetalle(enlace, evento.detail === 0);
    });

    document.addEventListener("keydown", function (evento) {
        if (evento.key !== "Escape" || evento.defaultPrevented || document.querySelector("dialog[open], [data-menu-contextual][open]")) return;
        var cerrar = contenido && contenido.querySelector("[data-agenda-cerrar]");
        if (!cerrar) return;
        evento.preventDefault();
        cargarDetalle(cerrar, Boolean(panel && panel.contains(document.activeElement)));
    });

    document.addEventListener("change", function (evento) {
        if (evento.target.matches("[data-agenda-sede] select")) {
            evento.target.form.requestSubmit();
        }
    });

    var tabla = document.querySelector("[data-agenda-tabla]");
    if (tabla) {
        var formato = new Intl.DateTimeFormat("en-CA", {
            timeZone: tabla.dataset.zonaHoraria,
            year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23",
        });
        function marcarHoraActual() {
            tabla = document.querySelector("[data-agenda-tabla]");
            if (!tabla) return;
            var partes = {};
            formato.formatToParts(new Date()).forEach(function (parte) { partes[parte.type] = parte.value; });
            var fecha = partes.year + "-" + partes.month + "-" + partes.day;
            var incluyeHoy = tabla.dataset.fechaAgenda === fecha;
            tabla.querySelectorAll("[data-hora-fila]").forEach(function (fila) {
                var actual = incluyeHoy && Number(fila.dataset.horaFila) === Number(partes.hour);
                fila.classList.toggle("agenda-hora-actual", actual);
                fila.querySelector(".agenda-ahora").hidden = !actual;
            });
        }
        marcarHoraActual();
        document.addEventListener("agenda:grilla-actualizada", marcarHoraActual);
        window.setInterval(marcarHoraActual, 30000);
    }
});
