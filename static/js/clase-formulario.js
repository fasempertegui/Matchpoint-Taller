document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.querySelector("[data-clase-formulario]");
    if (!formulario) return;

    function actualizarAvisoParticipantes() {
        var seccion = formulario.querySelector('[data-tipo="participantes"]');
        if (!seccion) return;
        var modalidad = formulario.querySelector('input[name="modalidad"]:checked');
        var cantidad = seccion.querySelectorAll("[data-persona]").length;
        var mensaje = "";
        if (modalidad && modalidad.value === "grupal" && cantidad > 6) {
            mensaje = "Superás el máximo recomendado de 6 participantes para una clase grupal.";
        } else if (modalidad && modalidad.value === "individual" && cantidad > 1) {
            mensaje = "La clase individual tiene " + cantidad + " participantes. Podés continuar si está acordado.";
        }
        seccion.querySelector("[data-mensaje-cantidad]").textContent = mensaje;
        seccion.querySelector("[data-aviso-cantidad]").hidden = !mensaje;
        seccion.querySelector("h2").classList.toggle("clase-contador-advertencia", Boolean(mensaje));
    }

    formulario.addEventListener("change", function (evento) {
        if (evento.target.name === "modalidad") actualizarAvisoParticipantes();
    });

    function idsSeleccionados() {
        return Array.from(formulario.querySelectorAll("[data-persona]"), function (fila) {
            return fila.dataset.persona;
        });
    }

    formulario.querySelectorAll("[data-selector-personas]").forEach(function (selector) {
        var entrada = selector.querySelector("[data-busqueda]");
        var resultados = selector.querySelector("[data-resultados]");
        var seleccionados = selector.querySelector("[data-seleccionados]");
        var estado = selector.querySelector("[data-estado]");
        var todos = selector.querySelector("[data-todos]");
        var solicitud = null;
        var demora = null;

        function cerrarResultados() {
            resultados.replaceChildren();
            resultados.hidden = true;
        }

        function actualizarCantidad() {
            var cantidad = seleccionados.children.length;
            selector.querySelector("[data-cantidad]").textContent = cantidad;
            selector.querySelector("[data-vacio]").hidden = cantidad > 0;
            actualizarAvisoParticipantes();
        }

        function agregar(persona) {
            if (idsSeleccionados().includes(String(persona.id))) {
                estado.textContent = "Esa persona ya está agregada a la clase.";
                return;
            }
            var fila = document.createElement("li");
            fila.dataset.persona = persona.id;
            var nombre = document.createElement("span");
            nombre.textContent = persona.nombre;
            var usuario = document.createElement("small");
            usuario.textContent = persona.usuario;
            nombre.append(usuario);
            var valor = document.createElement("input");
            valor.type = "hidden";
            valor.name = selector.dataset.tipo;
            valor.value = persona.id;
            var quitar = document.createElement("button");
            quitar.type = "button";
            quitar.className = "clase-quitar";
            quitar.dataset.quitar = "";
            quitar.setAttribute("aria-label", "Quitar a " + persona.nombre);
            quitar.textContent = "×";
            fila.append(nombre, valor, quitar);
            seleccionados.append(fila);
            if (solicitud) solicitud.abort();
            window.clearTimeout(demora);
            cerrarResultados();
            entrada.value = "";
            estado.textContent = persona.nombre + " agregado a " + selector.dataset.tipo + ".";
            actualizarCantidad();
            entrada.focus();
        }

        async function buscar() {
            var texto = entrada.value.trim();
            if (texto.length < 2) return;
            var actual = new AbortController();
            solicitud = actual;
            estado.textContent = "Buscando…";
            var url = new URL(selector.dataset.url, window.location.origin);
            url.searchParams.set("q", texto);
            url.searchParams.set("tipo", selector.dataset.tipo);
            if (todos && todos.checked) url.searchParams.set("todos", "1");
            idsSeleccionados().forEach(function (id) { url.searchParams.append("excluir", id); });
            try {
                var respuesta = await fetch(url, {signal: actual.signal, credentials: "same-origin", cache: "no-store"});
                if (!respuesta.ok || respuesta.redirected) throw new Error();
                var datos = await respuesta.json();
                if (solicitud !== actual || entrada.value.trim() !== texto) return;
                cerrarResultados();
                datos.resultados.forEach(function (persona) {
                    if (idsSeleccionados().includes(String(persona.id))) return;
                    var fila = document.createElement("li");
                    var boton = document.createElement("button");
                    boton.type = "button";
                    boton.textContent = persona.nombre;
                    var usuario = document.createElement("small");
                    usuario.textContent = persona.usuario;
                    boton.append(usuario);
                    boton.addEventListener("click", function () { agregar(persona); });
                    fila.append(boton);
                    resultados.append(fila);
                });
                var cantidad = resultados.children.length;
                resultados.hidden = cantidad === 0;
                estado.textContent = cantidad === 0 ? "Sin coincidencias disponibles." :
                    cantidad + " coincidencias. Elegí una para agregar.";
                if (datos.hay_mas) estado.textContent += " Hay más resultados: precisá la búsqueda.";
            } catch (error) {
                if (error.name !== "AbortError" && solicitud === actual) {
                    cerrarResultados();
                    estado.textContent = "No se pudo buscar. Volvé a escribir o recargá la página si tu sesión venció.";
                }
            }
        }

        function programarBusqueda() {
            window.clearTimeout(demora);
            if (solicitud) solicitud.abort();
            cerrarResultados();
            estado.textContent = "";
            if (entrada.value.trim().length >= 2) demora = window.setTimeout(buscar, 250);
        }

        entrada.addEventListener("input", programarBusqueda);
        if (todos) todos.addEventListener("change", programarBusqueda);
        seleccionados.addEventListener("click", function (evento) {
            var quitar = evento.target.closest("[data-quitar]");
            if (!quitar) return;
            quitar.closest("[data-persona]").remove();
            actualizarCantidad();
            estado.textContent = "Persona retirada de la selección.";
            entrada.focus();
        });
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
                if (solicitud) solicitud.abort();
                window.clearTimeout(demora);
                cerrarResultados();
                estado.textContent = "";
                entrada.focus();
            } else if (evento.key === "Enter" && evento.target === entrada) {
                evento.preventDefault();
                if (botones.length) botones[0].focus();
            }
        });
        document.addEventListener("click", function (evento) {
            if (!selector.contains(evento.target)) {
                if (solicitud) solicitud.abort();
                window.clearTimeout(demora);
                cerrarResultados();
                estado.textContent = "";
            }
        });
    });
    actualizarAvisoParticipantes();
});
