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

    function prepararOrganizador() {
        var selector = contenido && contenido.querySelector("[data-organizador-selector]");
        if (!selector) return;
        var entrada = selector.querySelector("[data-organizador-busqueda]");
        var campo = selector.querySelector('input[name="organizador"]');
        var seleccion = selector.querySelector("[data-organizador-seleccion]");
        var buscador = selector.querySelector("[data-organizador-buscador]");
        var nombre = selector.querySelector("[data-organizador-nombre]");
        var usuario = selector.querySelector("[data-organizador-usuario]");
        var resultados = selector.querySelector("[data-organizador-resultados]");
        var estado = selector.querySelector("[data-estado]");
        var solicitud = null;
        var demora = null;

        function limpiarBusqueda() {
            window.clearTimeout(demora);
            if (solicitud) solicitud.abort();
            resultados.replaceChildren();
            resultados.hidden = true;
            estado.textContent = "";
        }

        function quitar() {
            limpiarBusqueda();
            campo.value = "";
            nombre.textContent = "";
            usuario.textContent = "";
            entrada.value = "";
            seleccion.hidden = true;
            buscador.hidden = false;
        }

        function elegir(persona) {
            limpiarBusqueda();
            campo.value = persona.id;
            nombre.textContent = persona.nombre;
            usuario.textContent = persona.usuario;
            entrada.value = "";
            seleccion.hidden = false;
            buscador.hidden = true;
            selector.querySelector("[data-organizador-quitar]").focus();
        }

        async function buscar() {
            var texto = entrada.value.trim();
            if (texto.length < 2 || !selector.isConnected) return;
            var actual = new AbortController();
            solicitud = actual;
            estado.textContent = "Buscando…";
            var url = new URL(selector.dataset.url, window.location.origin);
            url.searchParams.set("q", texto);
            try {
                var respuesta = await fetch(url, {signal: actual.signal, credentials: "same-origin", cache: "no-store"});
                if (!respuesta.ok || respuesta.redirected) throw new Error();
                var datos = await respuesta.json();
                if (solicitud !== actual || entrada.value.trim() !== texto || !selector.isConnected) return;
                resultados.replaceChildren();
                datos.resultados.forEach(function (persona) {
                    var fila = document.createElement("li");
                    var boton = document.createElement("button");
                    boton.type = "button";
                    boton.textContent = persona.nombre;
                    var detalle = document.createElement("small");
                    detalle.textContent = persona.usuario;
                    boton.append(detalle);
                    boton.addEventListener("click", function () { elegir(persona); });
                    fila.append(boton);
                    resultados.append(fila);
                });
                resultados.hidden = datos.resultados.length === 0;
                estado.textContent = datos.resultados.length ? datos.resultados.length + " coincidencias. Elegí una para agregar." : "Sin coincidencias disponibles.";
                if (datos.hay_mas) estado.textContent += " Hay más resultados: precisá la búsqueda.";
            } catch (error) {
                if (error.name !== "AbortError" && solicitud === actual && selector.isConnected) {
                    estado.textContent = "No se pudo buscar. Volvé a escribir o recargá la página si tu sesión venció.";
                }
            }
        }

        entrada.addEventListener("input", function () {
            limpiarBusqueda();
            if (entrada.value.trim().length >= 2) demora = window.setTimeout(buscar, 250);
        });
        selector.querySelector("[data-organizador-quitar]").addEventListener("click", function () {
            quitar();
            entrada.focus();
        });
        selector.addEventListener("organizador:limpiar", quitar);
        selector.addEventListener("keydown", function (evento) {
            var botones = Array.from(resultados.querySelectorAll("button"));
            var indice = botones.indexOf(document.activeElement);
            if (evento.key === "ArrowDown" && botones.length) {
                evento.preventDefault();
                botones[(indice + 1) % botones.length].focus();
            } else if (evento.key === "ArrowUp" && indice >= 0) {
                evento.preventDefault();
                if (indice === 0) entrada.focus();
                else botones[indice - 1].focus();
            } else if (evento.key === "Escape") {
                limpiarBusqueda();
                if (!buscador.hidden) entrada.focus();
            } else if (evento.key === "Enter" && evento.target === entrada) {
                evento.preventDefault();
                if (botones.length) botones[0].focus();
            }
        });
    }

    function prepararCreacionTurno() {
        if (!contenido) return;
        var opciones = Array.from(contenido.querySelectorAll("[data-agenda-opcion-creacion]"));
        var formularios = opciones.filter(function (opcion) { return opcion.hasAttribute("data-agenda-creacion"); });
        if (!formularios.length) return;
        var titulo = contenido.querySelector("[data-agenda-titulo]");

        function actualizar() {
            var activa = formularios.find(function (opcion) { return opcion.open; });
            opciones.forEach(function (opcion) {
                opcion.hidden = Boolean(activa && opcion !== activa);
                if (opcion.hasAttribute("data-agenda-creacion")) opcion.querySelector("summary").hidden = opcion === activa;
            });
            titulo.textContent = activa ? (activa.dataset.agendaCreacion === "reserva" ? "Nueva reserva" : "Nuevo bloqueo") : "Turno libre";
        }

        formularios.forEach(function (opcion) {
            opcion.addEventListener("toggle", function () {
                actualizar();
                if (opcion.open) {
                    var campo = opcion.querySelector("[data-organizador-buscador]:not([hidden]) input")
                        || opcion.querySelector("select")
                        || opcion.querySelector("[data-agregar-observaciones]:not([hidden])")
                        || opcion.querySelector("textarea");
                    if (campo) campo.focus();
                }
            });
            opcion.querySelector("[data-cancelar-creacion]").addEventListener("click", function () {
                var formulario = opcion.querySelector("form");
                formulario.reset();
                formulario.querySelectorAll("select, textarea, input:not([type=hidden])").forEach(function (campo) {
                    if (campo.tagName === "SELECT") campo.selectedIndex = 0;
                    else if (campo.type === "checkbox" || campo.type === "radio") campo.checked = false;
                    else campo.value = "";
                });
                formulario.querySelectorAll(".error-campo, .errorlist").forEach(function (error) { error.remove(); });
                formulario.querySelectorAll("[data-observaciones]").forEach(function (bloque) {
                    bloque.dispatchEvent(new Event("observaciones:actualizar"));
                });
                var selector = formulario.querySelector("[data-organizador-selector]");
                if (selector) selector.dispatchEvent(new Event("organizador:limpiar"));
                opcion.open = false;
                actualizar();
                opcion.querySelector("summary").focus();
            });
        });
        actualizar();
    }

    function prepararConfirmacionReserva() {
        var formulario = document.querySelector("[data-agenda-reserva]");
        if (!formulario) return;
        var mensaje = formulario.dataset.confirmar;
        formulario.addEventListener("submit", function () {
            var organizador = formulario.elements.organizador;
            if (organizador && organizador.value) {
                formulario.dataset.confirmar = mensaje + "\n\nOrganizador: " + formulario.querySelector("[data-organizador-nombre]").textContent;
            }
        });
    }

    function prepararConfirmacionBloqueo() {
        var formulario = document.querySelector("[data-agenda-bloqueo]");
        if (!formulario) return;
        var mensaje = formulario.dataset.confirmar;
        formulario.addEventListener("submit", function () {
            var motivo = formulario.elements["bloqueo-motivo"];
            formulario.dataset.confirmar = mensaje + "\n\nMotivo: " + motivo.selectedOptions[0].textContent;
        });
    }

    function prepararCamposOperacion() {
        var formulario = document.querySelector("[data-agenda-operacion]");
        if (!formulario) return;

        function actualizarCampos() {
            var bloquear = formulario.elements.operacion.value === "bloquear";
            var variasCanchas = formulario.elements.seleccion_canchas.value === "seleccionar";
            formulario.querySelector("[data-operacion-varias-canchas]").hidden = !variasCanchas;
            formulario.querySelectorAll('input[name="canchas"]').forEach(function (cancha) {
                cancha.disabled = !variasCanchas;
            });
            var desde = formulario.elements.horario.value;
            var hasta = formulario.elements.hora_hasta;
            var finElegido = hasta.value;
            var opciones = [new Option("Fin del día", "")];
            if (desde !== "dia") {
                hasta.dataset.finalesHabilitados.split(",").forEach(function (valor) {
                    if (valor && valor > desde) opciones.push(new Option(valor, valor, false, valor === finElegido));
                });
            }
            hasta.replaceChildren(...opciones);
            hasta.disabled = desde === "dia";
            formulario.querySelector("[data-operacion-hasta]").hidden = desde === "dia";
            formulario.querySelector("[data-operacion-motivo-bloqueo]").hidden = !bloquear;
            formulario.elements.motivo_bloqueo.disabled = !bloquear;
            formulario.elements.motivo_bloqueo.required = bloquear;
            formulario.querySelector("[data-operacion-observaciones]").hidden = !bloquear;
            formulario.elements.observaciones.disabled = !bloquear;
            formulario.querySelector("[data-operacion-excluir-bloqueos]").hidden = bloquear;
            formulario.elements.excluir_bloqueos.disabled = bloquear;

        }

        formulario.addEventListener("change", actualizarCampos);
        actualizarCampos();
    }

    async function cargarDetalle(enlace, datosFormulario) {
        if (solicitudActual) solicitudActual.abort();
        var seleccionadoAnterior = document.querySelector(".agenda-turno-seleccionado") || document.querySelector("[data-agenda-acciones]");
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
            aviso.textContent = "Cargando…";
            aviso.hidden = false;
        }, 300);
        var mensajeError = "No se pudo cargar el panel. Intentá nuevamente.";
        try {
            var respuesta = await fetch(enlace.href || enlace.action, {
                method: datosFormulario ? "POST" : "GET",
                body: datosFormulario,
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
                if (respuesta.status === 403) mensajeError = "No se pudo autorizar la consulta. Recargá la página para continuar.";
                if (respuesta.status === 400) mensajeError = (await respuesta.json()).error;
                throw new Error();
            }
            var seleccion = respuesta.headers.get("X-Agenda-Seleccion");
            if (!seleccion) throw new Error();
            var html = await respuesta.text();
            if (solicitud !== solicitudActual) return;
            contenido.innerHTML = html;
            contenido.dispatchEvent(new Event("observaciones:inicializar", {bubbles: true}));
            prepararOrganizador();
            prepararCreacionTurno();
            prepararConfirmacionReserva();
            prepararConfirmacionBloqueo();
            prepararCamposOperacion();
            var botonAcciones = document.querySelector("[data-agenda-acciones]");
            if (botonAcciones) botonAcciones.setAttribute("aria-expanded", String(Boolean(contenido.querySelector("[data-agenda-panel-acciones]"))));
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
        var enlace = evento.target.closest("[data-agenda-turno], [data-agenda-cerrar], [data-agenda-acciones]");
        if (!enlace || !panel || evento.defaultPrevented || evento.button !== 0 || evento.ctrlKey || evento.metaKey || evento.shiftKey || evento.altKey) return;
        evento.preventDefault();
        cargarDetalle(enlace);
    });

    document.addEventListener("submit", function (evento) {
        var formulario = evento.target;
        if (!formulario.matches("[data-agenda-operacion-envio]") || evento.defaultPrevented || !panel) return;
        evento.preventDefault();
        cargarDetalle(formulario, new FormData(formulario));
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

    prepararOrganizador();
    prepararCreacionTurno();
    prepararConfirmacionReserva();
    prepararConfirmacionBloqueo();
    prepararCamposOperacion();
});
