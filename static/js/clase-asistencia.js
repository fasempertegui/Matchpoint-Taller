document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.querySelector("[data-asistencia-formulario]");
    if (!formulario) return;
    var filas = formulario.querySelector("[data-asistencia-filas]");
    var plantilla = document.querySelector("[data-asistencia-fila-nueva]");
    var editor = document.querySelector("[data-asistencia-editor]");
    var observaciones = editor.querySelector("textarea");
    var filaActual = null;
    var confirmacion = document.querySelector("[data-asistencia-confirmacion]");
    var cambioPendiente = null;
    var guardando = false;
    var estadoGuardado = formulario.querySelector("[data-estado-guardado]");
    var buscador = formulario.querySelector("[data-asistencia-buscador]");
    var entrada = buscador.querySelector("[data-busqueda]");
    var resultados = buscador.querySelector("[data-resultados]");
    var estadoBusqueda = buscador.querySelector("[data-estado-busqueda]");
    var solicitud = null;
    var demora = null;

    formulario.addEventListener("submit", function (evento) { evento.preventDefault(); });
    [editor, confirmacion].forEach(function (modal) {
        modal.addEventListener("cancel", function (evento) { if (guardando) evento.preventDefault(); });
    });
    function mostrarExitoGuardado(fila) {
        if (window.Mensajes) {
            window.Mensajes.mostrar({
                texto: "Asistencia de " + fila.dataset.nombre + " guardada",
                nivel: "success",
                clave: "asistencia-guardada",
            });
        }
    }

    function mostrarErrorGuardado(mensaje) {
        if (window.Mensajes) {
            window.Mensajes.mostrar({
                texto: mensaje,
                nivel: "error",
            });
        }
    }

    async function guardarFila(fila, estado, nota) {
        if (guardando) return { ok: false, cancelado: true };
        guardando = true;
        var controles = Array.from(formulario.querySelectorAll("button"))
            .concat(Array.from(editor.querySelectorAll("button")), Array.from(confirmacion.querySelectorAll("button")));
        controles.forEach(function (control) { control.disabled = true; });
        estadoGuardado.hidden = false;
        estadoGuardado.textContent = "Guardando asistencia…";
        formulario.setAttribute("aria-busy", "true");
        var datos = new FormData();
        datos.set("csrfmiddlewaretoken", formulario.elements.csrfmiddlewaretoken.value);
        datos.set("version", formulario.elements.version.value);
        datos.set("usuario", fila.dataset.usuario);
        datos.set("estado", estado);
        datos.set("observaciones", nota);
        try {
            var respuesta = await fetch(formulario.dataset.urlGuardar, {
                method: "POST", body: datos, credentials: "same-origin", cache: "no-store",
                headers: {"Accept": "application/json"},
            });
            if (respuesta.redirected || !(respuesta.headers.get("Content-Type") || "").includes("application/json")) {
                return {
                    ok: false,
                    corregible: false,
                    error: "No se pudo confirmar el guardado. Revisá tu sesión y recargá la asistencia.",
                };
            }
            var resultado = await respuesta.json();
            if (!respuesta.ok) {
                return {
                    ok: false,
                    corregible: respuesta.status === 400,
                    error: resultado.error || "No se pudo guardar la asistencia.",
                };
            }
            formulario.elements.version.value = resultado.version;
            campo(fila, "estado").value = resultado.estado;
            campo(fila, "observaciones").value = resultado.observaciones;
            fila.dataset.quitable = "false";
            pintarFila(fila);
            if (resultado.clase_finalizada) {
                var aviso = document.querySelector("[data-aviso-finalizacion]");
                if (aviso) aviso.hidden = true;
            }
            return { ok: true };
        } catch (error) {
            return {
                ok: false,
                corregible: false,
                error: error instanceof TypeError || error instanceof SyntaxError
                    ? "No se pudo confirmar el guardado. Recargá para consultar el estado actual"
                    : error.message || "No se pudo guardar la asistencia.",
            };
        } finally {
            guardando = false;
            estadoGuardado.hidden = true;
            estadoGuardado.textContent = "";
            formulario.removeAttribute("aria-busy");
            controles.forEach(function (control) { control.disabled = false; });
        }
    }
    function campo(fila, nombre) { return fila.querySelector('[name$="-' + nombre + '"]'); }
    function actualizarFilas() {
        Array.from(filas.children).forEach(function (fila, indice) {
            fila.querySelectorAll("[name]").forEach(function (control) {
                control.name = control.name.replace(/asistencias-\d+-/, "asistencias-" + indice + "-");
                control.id = control.id.replace(/asistencias-\d+-/, "asistencias-" + indice + "-");
            });
        });
        var cantidad = filas.children.length;
        formulario.elements["asistencias-TOTAL_FORMS"].value = cantidad;
        formulario.querySelector("[data-total-personas]").textContent = cantidad;
        formulario.querySelector("[data-asistencia-vacio]").hidden = cantidad > 0;
        formulario.querySelector("[data-asistencia-tabla]").hidden = cantidad === 0;
    }
    function pintarFila(fila) {
        var estado = campo(fila, "estado").value;
        fila.querySelectorAll("[data-asistencia-estado]").forEach(function (indicador) {
            indicador.hidden = indicador.dataset.asistenciaEstado !== estado;
        });
        fila.querySelectorAll("[data-marcar-asistencia]").forEach(function (boton) {
            boton.setAttribute("aria-pressed", String(boton.dataset.marcarAsistencia === estado));
        });
        var nota = fila.querySelector("[data-observacion]");
        nota.textContent = campo(fila, "observaciones").value;
        nota.hidden = !nota.textContent.trim();
    }
    function abrirEditor(fila) {
        if (guardando) return;
        var error = editor.querySelector("[data-error-observaciones]");
        error.hidden = true;
        error.textContent = "";
        filaActual = fila;
        editor.querySelector("[data-editor-nombre]").textContent = fila.dataset.nombre;
        observaciones.value = campo(fila, "observaciones").value;
        editor.querySelector("[data-quitar-de-carga]").hidden = fila.dataset.quitable !== "true";
        editor.showModal();
        editor.querySelector("[data-observaciones]").dispatchEvent(new Event("observaciones:actualizar"));
        editor.querySelector("[data-quitar-marca]").hidden = campo(fila, "estado").value === "sin_registrar";
    }
    filas.addEventListener("click", function (evento) {
        var boton = evento.target.closest("[data-editar-asistencia]");
        if (boton) abrirEditor(boton.closest("[data-asistencia-fila]"));
    });
    function solicitarCambio(fila, estado, origen) {
        if (guardando) return;
        cambioPendiente = {fila: fila, estado: estado, origen: origen};
        confirmacion.querySelector("[data-confirmacion-titulo]").textContent = estado === "sin_registrar"
            ? "Quitar marca de asistencia" : "Marcar " + (estado === "presente" ? "presente" : "ausente");
        confirmacion.querySelector("[data-confirmacion-mensaje]").textContent = estado === "sin_registrar"
            ? "¿Dejar sin registrar la asistencia de " + fila.dataset.nombre + "?"
            : "¿Marcar a " + fila.dataset.nombre + " como " + estado + "?";
        confirmacion.returnValue = "cancelar";
        confirmacion.showModal();
    }
    filas.addEventListener("click", function (evento) {
        var boton = evento.target.closest("[data-marcar-asistencia]");
        if (boton) solicitarCambio(boton.closest("[data-asistencia-fila]"), boton.dataset.marcarAsistencia, boton);
    });
    confirmacion.addEventListener("close", async function () {
        var cambio = cambioPendiente;
        cambioPendiente = null;
        if (!cambio || !cambio.fila.isConnected) return;
        if (confirmacion.returnValue === "confirmar") {
            var resultado = await guardarFila(cambio.fila, cambio.estado, campo(cambio.fila, "observaciones").value);
            if (resultado.ok) {
                mostrarExitoGuardado(cambio.fila);
            } else if (!resultado.cancelado) {
                mostrarErrorGuardado(resultado.error);
            }
        }
        cambio.origen.focus();
    });
    editor.querySelector("[data-quitar-marca]").addEventListener("click", function () {
        var fila = filaActual;
        editor.close();
        solicitarCambio(fila, "sin_registrar", fila.querySelector("[data-editar-asistencia]"));
    });
    editor.querySelector("form").addEventListener("submit", async function (evento) {
        if (!evento.submitter || evento.submitter.value !== "guardar") return;
        evento.preventDefault();
        if (!filaActual || guardando) return;
        var fila = filaActual;
        var error = editor.querySelector("[data-error-observaciones]");
        error.hidden = true;
        error.textContent = "";
        var resultado = await guardarFila(fila, campo(fila, "estado").value, observaciones.value);
        if (resultado.ok) {
            editor.close();
            mostrarExitoGuardado(fila);
        } else if (!resultado.cancelado) {
            if (resultado.corregible) {
                error.textContent = resultado.error;
                error.hidden = false;
                observaciones.focus();
            } else {
                mostrarErrorGuardado(resultado.error);
            }
        }
    });
    editor.querySelector("[data-quitar-de-carga]").addEventListener("click", function () {
        if (filaActual && filaActual.dataset.quitable === "true") {
            filaActual.remove();
            filaActual = null;
            actualizarFilas();
            editor.close();
            formulario.querySelector("[data-abrir-busqueda]").focus();
        }
    });
    editor.addEventListener("close", function () {
        if (filaActual && filaActual.isConnected) filaActual.querySelector("[data-editar-asistencia]").focus();
        filaActual = null;
    });
    formulario.querySelector("[data-abrir-busqueda]").addEventListener("click", function () {
        buscador.hidden = !buscador.hidden;
        this.setAttribute("aria-expanded", String(!buscador.hidden));
        if (!buscador.hidden) entrada.focus();
        else cerrarBusqueda();
    });
    function cerrarBusqueda() {
        if (solicitud) solicitud.abort();
        window.clearTimeout(demora);
        resultados.replaceChildren();
        resultados.hidden = true;
        estadoBusqueda.textContent = "";
    }
    function agregar(persona) {
        if (guardando) return;
        if (Array.from(filas.children).some(function (fila) { return fila.dataset.usuario === String(persona.id); })) return;
        var indice = filas.children.length;
        var contenedor = document.createElement("tbody");
        contenedor.innerHTML = plantilla.innerHTML.replaceAll("__prefix__", indice);
        var fila = contenedor.firstElementChild;
        fila.dataset.usuario = persona.id;
        fila.dataset.nombre = persona.nombre;
        fila.querySelector("[data-nombre]").textContent = persona.nombre;
        var usuarioNombre = fila.querySelector("[data-usuario-nombre]");
        if (usuarioNombre) {
            usuarioNombre.textContent = "@" + persona.usuario;
            usuarioNombre.hidden = false;
        }
        fila.querySelector("[data-editar-asistencia]").setAttribute("aria-label", "Observaciones de " + persona.nombre);
        campo(fila, "usuario").value = persona.id;
        campo(fila, "estado").value = "sin_registrar";
        filas.append(fila);
        actualizarFilas();
        pintarFila(fila);
        entrada.value = "";
        var botonBorrar = entrada.nextElementSibling;
        if (botonBorrar && botonBorrar.matches("[data-borrar-busqueda]")) botonBorrar.hidden = true;
        cerrarBusqueda();
        fila.querySelector("[data-marcar-asistencia]").focus();
    }
    async function buscar() {
        var texto = entrada.value.trim();
        if (texto.length < 2) return;
        var actual = new AbortController();
        solicitud = actual;
        var url = new URL(buscador.dataset.url, window.location.origin);
        url.searchParams.set("q", texto);
        Array.from(filas.children).forEach(function (fila) { url.searchParams.append("excluir", fila.dataset.usuario); });
        estadoBusqueda.textContent = "Buscando…";
        try {
            var respuesta = await fetch(url, {signal: actual.signal, credentials: "same-origin", cache: "no-store"});
            if (!respuesta.ok || respuesta.redirected) throw new Error();
            var datos = await respuesta.json();
            if (solicitud !== actual || entrada.value.trim() !== texto || buscador.hidden) return;
            resultados.replaceChildren();
            datos.resultados.forEach(function (persona) {
                if (Array.from(filas.children).some(function (fila) { return fila.dataset.usuario === String(persona.id); })) return;
                var fila = document.createElement("li");
                var boton = document.createElement("button");
                boton.type = "button";
                boton.textContent = persona.nombre;
                var usuario = document.createElement("small");
                usuario.textContent = persona.usuario + (persona.activa ? "" : " · Cuenta inactiva");
                boton.append(usuario);
                boton.addEventListener("click", function () { agregar(persona); });
                fila.append(boton);
                resultados.append(fila);
            });
            resultados.hidden = resultados.children.length === 0;
            estadoBusqueda.textContent = resultados.hidden ? "Sin coincidencias disponibles." : "Elegí una persona para agregar.";
            if (datos.hay_mas) estadoBusqueda.textContent += " Hay más resultados: precisá la búsqueda.";
        } catch (error) {
            if (error.name !== "AbortError" && solicitud === actual) estadoBusqueda.textContent = "No se pudo buscar. Volvé a escribir o recargá la página si tu acceso cambió.";
        }
    }
    entrada.addEventListener("input", function () {
        cerrarBusqueda();
        if (entrada.value.trim().length >= 2) demora = window.setTimeout(buscar, 250);
    });
    buscador.addEventListener("keydown", function (evento) {
        var botones = Array.from(resultados.querySelectorAll("button"));
        var indice = botones.indexOf(document.activeElement);
        if (evento.key === "ArrowDown" && botones.length) {
            evento.preventDefault(); botones[(indice + 1) % botones.length].focus();
        } else if (evento.key === "ArrowUp" && indice >= 0) {
            evento.preventDefault(); if (indice === 0) entrada.focus(); else botones[indice - 1].focus();
        } else if (evento.key === "Escape") {
            cerrarBusqueda(); entrada.focus();
        } else if (evento.key === "Enter" && evento.target === entrada) {
            evento.preventDefault(); if (botones.length) botones[0].focus();
        }
    });
});
