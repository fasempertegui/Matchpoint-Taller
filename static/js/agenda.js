document.addEventListener("DOMContentLoaded", function () {
    var filtros = document.querySelector("[data-agenda-filtros]");
    if (filtros) {
        filtros.addEventListener("change", function () {
            filtros.requestSubmit();
        });
    }

    var panel = document.querySelector("[data-agenda-detalle]");
    var contenido = panel && panel.querySelector("[data-agenda-contenido]");
    var aviso = panel && panel.querySelector("[data-agenda-aviso]");
    var solicitudActual = null;

    function prepararConfirmacionReserva() {
        var formulario = document.querySelector("[data-agenda-reserva]");
        if (!formulario) return;
        var mensaje = formulario.dataset.confirmar;
        formulario.addEventListener("submit", function () {
            var organizador = formulario.elements.organizador;
            if (organizador.value) {
                formulario.dataset.confirmar = mensaje + "\n\nOrganizador: " + organizador.selectedOptions[0].textContent;
            }
        });
    }

    async function cargarDetalle(enlace) {
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
            aviso.setAttribute("role", "status");
            aviso.textContent = "Cargando turno…";
            aviso.hidden = false;
        }, 300);
        var mensajeError = "No se pudo cargar el turno. Intentá seleccionarlo nuevamente.";
        try {
            var respuesta = await fetch(enlace.href, {
                headers: {"X-Agenda-Detalle": "1"},
                credentials: "same-origin",
                cache: "no-store",
                signal: solicitud.signal,
            });
            if (respuesta.redirected) {
                mensajeError = "Tu acceso cambió o la sesión venció. Recargá la página para continuar.";
                throw new Error();
            }
            if (!respuesta.ok) {
                if (respuesta.status === 403) mensajeError = "No tenés acceso al detalle de este turno.";
                if (respuesta.status === 400) mensajeError = (await respuesta.json()).error;
                throw new Error();
            }
            var seleccion = respuesta.headers.get("X-Agenda-Seleccion");
            if (!seleccion) throw new Error();
            var html = await respuesta.text();
            if (solicitud !== solicitudActual) return;
            contenido.innerHTML = html;
            prepararConfirmacionReserva();
            var destino = new URL(seleccion, window.location.href);
            document.querySelectorAll("[data-agenda-turno]").forEach(function (turno) {
                var activo = turno.pathname === destino.pathname && turno.search === destino.search;
                turno.classList.toggle("agenda-turno-seleccionado", activo);
                if (activo) turno.setAttribute("aria-current", "true");
                else turno.removeAttribute("aria-current");
            });
            window.history.replaceState(null, "", destino.href);
            if (cerrarDetalle && seleccionadoAnterior) seleccionadoAnterior.focus({preventScroll: true});
            aviso.hidden = true;
            aviso.textContent = "";
        } catch (error) {
            if (error.name === "AbortError" || solicitud !== solicitudActual) return;
            aviso.setAttribute("role", "alert");
            aviso.textContent = mensajeError;
            aviso.hidden = false;
        } finally {
            window.clearTimeout(demoraAviso);
            if (solicitud === solicitudActual) {
                panel.removeAttribute("aria-busy");
                contenido.inert = false;
            }
        }
    }

    document.addEventListener("click", function (evento) {
        var enlace = evento.target.closest("[data-agenda-turno], [data-agenda-cerrar]");
        if (!enlace || !panel || evento.defaultPrevented || evento.button !== 0 || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey) return;
        evento.preventDefault();
        cargarDetalle(enlace);
    });

    var tabla = document.querySelector("[data-agenda-tabla]");
    if (tabla) {
        var formato = new Intl.DateTimeFormat("en-CA", {
            timeZone: tabla.dataset.zonaHoraria,
            year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23",
        });
        function marcarHoraActual() {
            var partes = {};
            formato.formatToParts(new Date()).forEach(function (parte) { partes[parte.type] = parte.value; });
            var fecha = partes.year + "-" + partes.month + "-" + partes.day;
            var incluyeHoy = false;
            tabla.querySelectorAll("[data-fecha-columna]").forEach(function (columna) {
                var hoy = columna.dataset.fechaColumna === fecha;
                columna.classList.toggle("agenda-columna-hoy", hoy);
                if (hoy) incluyeHoy = true;
            });
            tabla.querySelectorAll("[data-hora-fila]").forEach(function (fila) {
                var actual = incluyeHoy && Number(fila.dataset.horaFila) === Number(partes.hour);
                fila.classList.toggle("agenda-hora-actual", actual);
                fila.querySelector(".agenda-ahora").hidden = !actual;
            });
        }
        marcarHoraActual();
        window.setInterval(marcarHoraActual, 30000);
    }

    prepararConfirmacionReserva();
});
