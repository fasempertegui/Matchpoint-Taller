document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.querySelector("[data-asistencia-formulario]");
    if (!formulario) return;
    var filas = formulario.querySelector("[data-asistencia-filas]");
    var plantilla = document.querySelector("[data-asistencia-fila-nueva]");
    var editor = document.querySelector("[data-asistencia-editor]");
    var observaciones = editor.querySelector("textarea");
    var filaActual = null;
    var buscador = formulario.querySelector("[data-asistencia-buscador]");
    var entrada = buscador.querySelector("[data-busqueda]");
    var resultados = buscador.querySelector("[data-resultados]");
    var estadoBusqueda = buscador.querySelector("[data-estado-busqueda]");
    var solicitud = null;
    var demora = null;
    var etiquetas = {presente: "Presente", ausente: "Ausente", sin_registrar: "Sin registrar"};

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
        formulario.querySelector("[data-guardar-asistencia]").hidden = cantidad === 0;
    }
    function pintarFila(fila) {
        var estado = campo(fila, "estado").value;
        var badge = fila.querySelector("[data-badge]");
        badge.className = "badge-estado badge-estado-" + (estado === "presente" ? "activo" : "inactivo");
        badge.textContent = etiquetas[estado] || "Sin registrar";
        var nota = fila.querySelector("[data-observacion]");
        nota.textContent = campo(fila, "observaciones").value;
        nota.hidden = !nota.textContent.trim();
    }
    function abrirEditor(fila) {
        filaActual = fila;
        editor.querySelector("[data-editor-nombre]").textContent = fila.dataset.nombre;
        editor.querySelectorAll('input[name="editor-estado"]').forEach(function (opcion) {
            opcion.checked = opcion.value === campo(fila, "estado").value;
        });
        observaciones.value = campo(fila, "observaciones").value;
        editor.querySelector("[data-quitar-de-carga]").hidden = fila.dataset.quitable !== "true";
        editor.showModal();
        editor.querySelector("[data-observaciones]").dispatchEvent(new Event("observaciones:actualizar"));
        var elegido = editor.querySelector('input[name="editor-estado"]:checked');
        if (elegido) elegido.focus();
    }
    filas.addEventListener("click", function (evento) {
        var boton = evento.target.closest("[data-editar-asistencia]");
        if (boton) abrirEditor(boton.closest("[data-asistencia-fila]"));
    });
    editor.addEventListener("change", function (evento) {
        if (filaActual && evento.target.name === "editor-estado") {
            campo(filaActual, "estado").value = evento.target.value;
            pintarFila(filaActual);
        }
    });
    observaciones.addEventListener("input", function () {
        if (!filaActual) return;
        campo(filaActual, "observaciones").value = observaciones.value;
        pintarFila(filaActual);
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
        if (Array.from(filas.children).some(function (fila) { return fila.dataset.usuario === String(persona.id); })) return;
        var indice = filas.children.length;
        var contenedor = document.createElement("tbody");
        contenedor.innerHTML = plantilla.innerHTML.replaceAll("__prefix__", indice);
        var fila = contenedor.firstElementChild;
        fila.dataset.usuario = persona.id;
        fila.dataset.nombre = persona.nombre;
        fila.querySelector("[data-nombre]").textContent = persona.nombre;
        fila.querySelector("[data-editar-asistencia]").setAttribute("aria-label", "Editar asistencia de " + persona.nombre);
        campo(fila, "usuario").value = persona.id;
        campo(fila, "estado").value = "sin_registrar";
        filas.append(fila);
        actualizarFilas();
        pintarFila(fila);
        entrada.value = "";
        cerrarBusqueda();
        abrirEditor(fila);
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
