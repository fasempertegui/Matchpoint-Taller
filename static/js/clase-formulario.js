document.addEventListener("DOMContentLoaded", function () {
    function crearIconoCruz() {
        var ns = "http://www.w3.org/2000/svg";
        var svg = document.createElementNS(ns, "svg");
        svg.setAttribute("aria-hidden", "true");
        svg.setAttribute("focusable", "false");
        svg.setAttribute("width", "24");
        svg.setAttribute("height", "24");
        svg.setAttribute("stroke-width", "1.5");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("fill", "none");
        var path = document.createElementNS(ns, "path");
        path.setAttribute("d", "M6.75827 17.2426L12.0009 12M17.2435 6.75736L12.0009 12M12.0009 12L6.75827 6.75736M12.0009 12L17.2435 17.2426");
        path.setAttribute("stroke", "currentColor");
        path.setAttribute("stroke-linecap", "round");
        path.setAttribute("stroke-linejoin", "round");
        svg.append(path);
        return svg;
    }

    function preparar(raiz) {
        raiz.querySelectorAll("[data-clase-formulario]").forEach(prepararFormulario);
    }

    function prepararFormulario(formulario) {
        if (formulario.dataset.clasePreparado) return;
        formulario.dataset.clasePreparado = "true";
        var ciclo = new AbortController();
        formulario.addEventListener("clase:desmontar", function () { ciclo.abort(); }, {once: true});

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
                seleccionados.hidden = cantidad === 0;
                selector.querySelector("[data-cantidad]").textContent = cantidad;
                var vacio = selector.querySelector("[data-vacio]");
                if (vacio) vacio.hidden = cantidad > 0;
                formulario.dispatchEvent(new Event("clase:seleccion"));
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
                quitar.className = "boton boton-utilidad boton-icono boton-chico clase-quitar";
                quitar.dataset.quitar = "";
                quitar.setAttribute("aria-label", "Quitar a " + persona.nombre);
                quitar.append(crearIconoCruz());
                fila.append(nombre, valor, quitar);
                seleccionados.append(fila);
                if (solicitud) solicitud.abort();
                window.clearTimeout(demora);
                cerrarResultados();
                entrada.value = "";
                var botonBorrar = entrada.nextElementSibling;
                if (botonBorrar && botonBorrar.matches("[data-borrar-busqueda]")) botonBorrar.hidden = true;
                estado.textContent = "";
                actualizarCantidad();
                entrada.focus();
            }

            async function buscar() {
                var texto = entrada.value.trim();
                if (texto.length < 2 || !selector.isConnected) return;
                var actual = new AbortController();
                solicitud = actual;
                selector.setAttribute("aria-busy", "true");
                estado.textContent = "Buscando…";
                var url = new URL(selector.dataset.url, window.location.origin);
                url.searchParams.set("q", texto);
                url.searchParams.set("tipo", selector.dataset.tipo);
                if (selector.dataset.planilla === "1") url.searchParams.set("planilla", "1");
                if (todos && todos.checked) url.searchParams.set("todos", "1");
                idsSeleccionados().forEach(function (id) { url.searchParams.append("excluir", id); });
                try {
                    var respuesta = await fetch(url, {signal: actual.signal, credentials: "same-origin", cache: "no-store"});
                    if (!respuesta.ok || respuesta.redirected) throw new Error();
                    var datos = await respuesta.json();
                    if (solicitud !== actual || entrada.value.trim() !== texto || !selector.isConnected) return;
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
                        if (persona.plan || persona.continuidad) {
                            var comercial = document.createElement("small");
                            if (persona.plan) comercial.append(document.createTextNode(persona.plan));
                            if (persona.continuidad) {
                                if (persona.plan) comercial.append(document.createTextNode(" — "));
                                var continuidad = document.createElement("span");
                                continuidad.textContent = persona.continuidad;
                                if (persona.continuidad_tono === "advertencia") {
                                    continuidad.className = "clase-resultado-continuidad-advertencia";
                                }
                                comercial.append(continuidad);
                            }
                            boton.append(comercial);
                        }
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
                    if (error.name !== "AbortError" && solicitud === actual && selector.isConnected) {
                        cerrarResultados();
                        estado.textContent = "No se pudo buscar. Volvé a escribir o recargá la página si tu sesión venció.";
                    }
                } finally {
                    if (solicitud === actual) selector.removeAttribute("aria-busy");
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
                estado.textContent = "";
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
                } else if (evento.key === "Escape" && !resultados.hidden) {
                    evento.preventDefault();
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
                if (!evento.composedPath().includes(selector)) {
                    if (solicitud) solicitud.abort();
                    window.clearTimeout(demora);
                    cerrarResultados();
                    estado.textContent = "";
                }
            }, {signal: ciclo.signal});
            formulario.addEventListener("clase:reiniciar", function () {
                if (solicitud) solicitud.abort();
                window.clearTimeout(demora);
                cerrarResultados();
                estado.textContent = "";
                actualizarCantidad();
            });
            actualizarCantidad();
            ciclo.signal.addEventListener("abort", function () {
                if (solicitud) solicitud.abort();
                window.clearTimeout(demora);
            }, {once: true});
        });
    }

    preparar(document);
    document.addEventListener("clase:inicializar", function (evento) { preparar(evento.target); });
});
